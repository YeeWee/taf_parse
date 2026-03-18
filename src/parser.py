"""
TAF 解析器核心逻辑
"""

import re
from datetime import datetime
from typing import Optional, List, Iterator, Tuple
from copy import deepcopy

try:
    from .models import TAF, WeatherState, ChangeGroup, Wind, Cloud, TAFDisplay, TEMPODetail, WindShear
    from .utils import parse_ddhhmm, parse_ddhhddhh
except ImportError:
    from models import TAF, WeatherState, ChangeGroup, Wind, Cloud, TAFDisplay, TEMPODetail, WindShear
    from utils import parse_ddhhmm, parse_ddhhddhh


class TAFParseError(Exception):
    """TAF 解析错误"""
    pass


def parse_taf(taf_text: str) -> TAF:
    """
    解析 TAF 文本

    Args:
        taf_text: 原始 TAF 报文字符串

    Returns:
        TAF 对象
    """
    # 标准化：去除多余空白，按行分割
    lines = [line.strip() for line in taf_text.strip().split('\n') if line.strip()]
    tokens = []
    for line in lines:
        # 检查是否包含 TAF 标记
        if 'TAF' in line.upper():
            # 提取 TAF 标记之后的内容
            # 处理格式：FTDL31 EDZO 132300 TAF EDDF ...
            # 以及：TAF AMD YSSY ... (修订报)、TAF COR ... (更正报)
            taf_match = re.search(r'\bTAF\s+(?:AMD\s+|COR\s+)?(.*)', line, flags=re.IGNORECASE)
            if taf_match:
                line = taf_match.group(1)
            else:
                # 没有找到 TAF 后的内容，跳过此行
                continue
        else:
            # 不含 TAF 标记的行，检查是否是 WMO 报头
            if re.match(r'^[A-Z0-9]{4,}\s+[A-Z]{3,4}\s+\d{6}\s*$', line, flags=re.IGNORECASE):
                continue
            # 检查是否以 4 字母 ICAO 开头，或者以变化组标记开头（TEMPO/INTER/BECMG/PROB 等）
            if not re.match(r'^[A-Z]{4}\s', line):
                # 检查是否是变化组行（包括 FMddhhmm 格式）
                # FMddhhmm: FM 后跟 6 位数字 (DDHHMM)
                if not re.match(r'^(TEMPO|INTER|BECMG|PROB\d{2}|FM\d{6})\s', line, flags=re.IGNORECASE):
                    continue

        # 移除 TAF 开头标记（包括 TAF AMD 修订报、TAF COR 更正报）
        # 根据《民用航空气象报文规范》附录二 2.1
        line = re.sub(r'^TAF\s+(AMD\s+|COR\s+)?', '', line, flags=re.IGNORECASE)
        # 移除报文结束标记 = （可能附在最后一个 token 后面，如 3000=）
        line = line.replace('=', ' ')
        tokens.extend(line.split())

    if not tokens:
        raise TAFParseError("空的 TAF 报文")

    # 创建迭代器便于逐个处理
    token_iter = iter(tokens)

    # 解析报文头
    try:
        icao = next(token_iter)
        issue_time_str = next(token_iter)
        validity_str = next(token_iter)
    except StopIteration:
        raise TAFParseError("TAF 报文格式不完整，缺少必要的头部信息")

    # 验证 ICAO 代码
    icao = icao.upper()
    if len(icao) != 4 or not icao.isalpha():
        raise TAFParseError(f"无效的 ICAO 代码：{icao}")

    # 解析发布时间
    issue_time = parse_issue_time(issue_time_str)

    # 解析有效期
    valid_from, valid_to = parse_validity(validity_str, issue_time)

    # 解析初始天气状态
    initial, remaining_tokens = parse_weather_state(token_iter, valid_from, valid_to)

    # 解析变化组
    changes = []
    current_token_iter = iter(remaining_tokens)

    while True:
        try:
            token = next(current_token_iter)
        except StopIteration:
            break

        # 检查是否是变化组开始
        # 注意：FM 可能带时间（如 FM090600），需要特殊处理
        change_type = token
        is_change_group = False

        # 标准变化组类型（单独出现）
        if token in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER'):
            is_change_group = True
        # PROBxx 格式（如 PROB30、PROB40）
        elif token.startswith('PROB') and len(token) > 4 and token[4:].isdigit():
            change_type = 'PROB'  # 规范化为 PROB
            is_change_group = True
        # INTER 后跟概率值的情况（罕见）
        elif token.startswith('INTER') and len(token) > 5:
            change_type = 'INTER'
            is_change_group = True
        # FM 带时间格式（如 FM150800）
        elif token.startswith('FM') and len(token) > 2 and token[2:].isdigit():
            is_change_group = True
        else:
            change_type = None

        if is_change_group:
            change_group, remaining = parse_change_group(
                token, current_token_iter, issue_time, valid_from, valid_to
            )
            if change_group:
                changes.append(change_group)
            current_token_iter = iter(remaining)
        elif token.startswith('TX') or token.startswith('TN'):
            # 温度预报，暂时跳过
            pass
        else:
            # 其他标记，跳过
            pass

    return TAF(
        raw=taf_text,
        icao=icao,
        issue_time=issue_time,
        valid_from=valid_from,
        valid_to=valid_to,
        initial=initial,
        changes=changes
    )


def parse_issue_time(time_str: str) -> datetime:
    """
    解析发布时间，格式 DDHHMMZ

    根据 TAF 规范，发布日期只有日、时、分，没有月份和年份。
    月份和年份根据当前日期推断。
    """
    if not time_str.upper().endswith('Z'):
        raise TAFParseError(f"发布时间格式错误，应以 Z 结尾：{time_str}")
    return parse_ddhhmm(time_str[:-1], datetime.utcnow())


def parse_validity(validity_str: str, base_date: datetime) -> Tuple[datetime, datetime]:
    """解析有效期，格式 DDHH/DDHH"""
    try:
        return parse_ddhhddhh(validity_str, base_date)
    except Exception as e:
        raise TAFParseError(f"无效的有效期格式：{validity_str}") from e


def parse_weather_state(
    token_iter: Iterator[str],
    period_start: datetime,
    period_end: datetime
) -> Tuple[WeatherState, List[str]]:
    """
    解析天气状态

    Returns:
        (WeatherState, 剩余的 tokens)
    """
    weather = WeatherState()
    remaining = []

    # 可能的天气元素
    wind_parsed = False
    visibility_parsed = False

    # 将 token_iter 转换为 list 便于向前 lookahead
    tokens_list = list(token_iter)
    i = 0

    while i < len(tokens_list):
        token = tokens_list[i]

        # 检查是否遇到变化组开始标记
        if token in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER', 'TX', 'TN'):
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(tokens_list[i + 1:])
            break
        # 检查是否是 PROB 带概率（如 PROB30、PROB40）
        if token.startswith('PROB') and len(token) > 4 and token[4:].isdigit():
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(tokens_list[i + 1:])
            break

        # 检查是否是 FM 开头带时间的标记（如 FM090600）- 必须在解析天气元素之前检查
        if token.startswith('FM') and len(token) > 2 and token[2:].isdigit():
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(tokens_list[i + 1:])
            break

        # 检查是否遇到备注标记，跳过后续内容
        if token in ('RMK', 'NXT', 'FCST', 'BY'):
            # 跳过备注部分
            remaining.extend(tokens_list[i + 1:])
            break

        # 尝试解析风
        if not wind_parsed and is_wind_token(token):
            weather.wind = parse_wind(token)
            wind_parsed = True
            i += 1
            continue

        # 尝试解析能见度
        # 检查是否是带整数部分的分数格式（如 "1" + "1/2SM"）
        if not visibility_parsed and is_visibility_fraction_start(token):
            next_token = tokens_list[i + 1] if i + 1 < len(tokens_list) else None
            if next_token and next_token.endswith('SM') and '/' in next_token:
                # 合并处理：z x/ySM 格式
                vis = parse_visibility_with_fraction(token, next_token)
                if vis is not None:
                    weather.visibility = vis
                    visibility_parsed = True
                    i += 2  # 跳过两个 token
                    continue

        # 尝试解析标准能见度格式
        if not visibility_parsed and is_visibility_token(token):
            if token == 'CAVOK':
                weather.cavok = True
                weather.visibility = 10000
            else:
                vis = parse_visibility(token)
                if vis is not None:
                    weather.visibility = vis
            visibility_parsed = True
            i += 1
            continue

        # 尝试解析天气现象
        if is_weather_token(token):
            weather.weather.append(token)
            i += 1
            continue

        # 尝试解析云
        if is_cloud_token(token):
            cloud = parse_cloud(token)
            if cloud:
                weather.clouds.append(cloud)
            i += 1
            continue

        # NSW - No Significant Weather
        if token == 'NSW':
            weather.weather = []
            i += 1
            continue

        # NCD - No Cloud Detected
        if token == 'NCD':
            weather.clouds = []
            i += 1
            continue

        # 风切变预报
        if is_wind_shear_token(token):
            wind_shear = parse_wind_shear(token)
            if wind_shear:
                if weather.wind is None:
                    weather.wind = Wind()
                weather.wind.wind_shear = wind_shear
            i += 1
            continue

        # 未知 token，可能是变化组的一部分，保存起来
        remaining.append(token)
        i += 1

    return weather, remaining


def is_wind_token(token: str) -> bool:
    """判断是否是风组"""
    # 格式：dddffMPS, dddffGffMPS, VRBffMPS, 或 KT 结尾
    if token.endswith(('MPS', 'KT')):
        return True
    # 也可能单独出现风向风速
    if len(token) >= 5 and token[:5].isdigit():
        return True
    if token.startswith('VRB') and len(token) > 3:
        return True
    return False


def parse_wind(token: str) -> Optional[Wind]:
    """解析风组"""
    wind = Wind()

    # 提取单位
    unit = 'MPS'
    if token.endswith('KT'):
        unit = 'KT'
        token = token[:-2]
    elif token.endswith('MPS'):
        token = token[:-3]

    # 解析阵风
    gust_match = re.search(r'G(\d+)', token)
    if gust_match:
        gust_value = int(gust_match.group(1))
        # 阵风值也需要单位转换
        if unit == 'KT':
            wind.gust = int(gust_value * 0.514444)
        else:
            wind.gust = gust_value
        token = token[:gust_match.start()] + token[gust_match.end():]

    # 解析风向和风速
    if token.startswith('VRB'):
        wind.variable = True
        remaining = token[3:]  # 去掉 "VRB"
        # 提取单位后缀
        if remaining.endswith(unit):
            speed_str = remaining[:-len(unit)]
        else:
            speed_str = remaining
    else:
        # 前 3 位是风向，后 2 位是风速
        if len(token) >= 5:
            dir_str = token[:3]
            speed_str = token[3:]
            if dir_str.isdigit():
                wind.direction = int(dir_str)

    if speed_str and speed_str.isdigit():
        speed = int(speed_str)
        if unit == 'KT':
            # 转换为 m/s
            speed = int(speed * 0.514444)
        wind.speed = speed

    return wind


def is_visibility_token(token: str) -> bool:
    """判断是否是能见度或 CAVOK"""
    if token == 'CAVOK':
        return True
    # 米制：纯数字，如 6000、1500（至少 2 位，避免与带分数整数部分混淆）
    if token.isdigit() and 2 <= len(token) <= 4:
        return True
    # 英制：如 P6SM、5SM、1/2SM、3/4SM 等
    if token.endswith('SM'):
        return True
    # 单个数字（0-9）可能是带分数能见度的整数部分，但不在此处处理
    # 需要在 parse_weather_state 中通过 lookahead 检查
    return False


def is_visibility_fraction_start(token: str) -> bool:
    """
    判断是否是能见度带整数部分的开头（如 "1" 在 "1 1/2SM" 中）

    北美 TAF 报文中常见格式：z x/ySM，如 "1 1/2SM"、"2 1/4SM"
    分割后变成 ["1", "1/2SM"]，需要合并处理
    """
    # 0-9 的整数可能是带分数能见度的整数部分
    if token.isdigit() and int(token) <= 9:
        return True
    return False


def parse_visibility(token: str) -> Optional[int]:
    """
    解析能见度，返回米

    Args:
        token: 能见度 token，如 '6000'、'P6SM'、'5SM'、'1/2SM'、'1 1/2SM'

    Returns:
        能见度（米）
    """
    if token == 'CAVOK':
        return 10000

    # 米制
    if token.isdigit():
        return int(token)

    # 英制（以 SM 结尾）
    if token.endswith('SM'):
        value_str = token[:-2]

        # P6SM = 大于 6 英里
        if value_str.startswith('P'):
            miles = float(value_str[1:])
            return int(miles * 1609.34)  # 转换为米

        # 分数形式：1/2SM、3/4SM
        if '/' in value_str:
            num, denom = value_str.split('/')
            miles = float(num) / float(denom)
            return int(miles * 1609.34)

        # 整数或小数：5SM、2.5SM
        miles = float(value_str)
        return int(miles * 1609.34)

    return None


def parse_visibility_with_fraction(int_part: str, frac_part: str) -> Optional[int]:
    """
    解析带整数部分的分数能见度格式（北美报文特有）

    格式：z x/ySM，如：
    - "1" + "1/2SM" = 1 又 1/2 英里 = 1.5 英里
    - "2" + "1/4SM" = 2 又 1/4 英里 = 2.25 英里

    Args:
        int_part: 整数部分，如 "1"
        frac_part: 分数部分（含 SM），如 "1/2SM"

    Returns:
        能见度（米）
    """
    if not frac_part.endswith('SM'):
        return None

    value_str = frac_part[:-2]  # 去掉 SM

    if '/' not in value_str:
        return None

    num, denom = value_str.split('/')

    try:
        int_value = int(int_part)
        frac_value = float(num) / float(denom)
        miles = int_value + frac_value
        return int(miles * 1609.34)
    except (ValueError, ZeroDivisionError):
        return None


def is_weather_token(token: str) -> bool:
    """
    判断是否是天气现象

    根据《民用航空气象报文规范》规定的天气现象代码
    """
    # 跳过备注标记和非法代码
    if token in ('RMK', 'NXT', 'FCST', 'BY', 'AUTO', 'NCD'):
        return False

    # 天气现象代码（按文档分类）
    weather_prefixes = ('-', '+', 'VC', 'RE', 'MI', 'PR', 'BC', 'DR', 'BL', 'SH', 'TS', 'FZ')
    weather_codes = (
        # 降水类
        'DZ', 'RA', 'SN', 'SG', 'IC', 'PL', 'GR', 'GS', 'UP',
        # 视程障碍现象类
        'FG', 'BR', 'FU', 'VA', 'DU', 'SA', 'HZ',
        # 其他类
        'PO', 'SQ', 'FC', 'SS', 'DS',
        # 无重要天气
        'NSW'
    )

    # 移除强度前缀
    test_token = token
    if test_token.startswith(('+', '-')):
        test_token = test_token[1:]

    # 检查是否以天气代码开头（精确匹配）
    for prefix in weather_prefixes:
        if test_token.startswith(prefix):
            # TS 需要特殊处理，避免匹配 FCST 等
            if prefix == 'TS':
                # TS 后面应该跟降水类型或单独出现
                remaining = test_token[2:]
                if remaining == '' or remaining in weather_codes:
                    return True
                # 检查是否是有效组合如 TSRA、TSSN 等
                if remaining in ('RA', 'SN', 'GR', 'GS', 'PL', 'SG', 'DZ'):
                    return True
                return False
            elif len(test_token) == len(prefix) or test_token[len(prefix):len(prefix)+2] in weather_codes:
                return True
            elif len(test_token) == len(prefix):
                return True

    # 检查是否包含完整天气代码
    for code in weather_codes:
        if test_token == code or (code in test_token and len(test_token) <= 6):
            return True

    return False


def is_wind_shear_token(token: str) -> bool:
    """判断是否是风切变组"""
    # 格式：WShhh/wwwddffKT 或 WShhh/wwwddffMPS
    # WS020/21045KT = 高度 200 英尺，风向 210 度，风速 45 节
    if token.startswith('WS'):
        remaining = token[2:]
        # 检查格式：hhh/wwwddff 单位
        if '/' in remaining:
            parts = remaining.split('/')
            if len(parts) == 2:
                height_part = parts[0]
                wind_part = parts[1]
                # 高度应该是 3 位数字
                if height_part.isdigit() and len(height_part) == 3:
                    # 风速部分应该以 KT 或 MPS 结尾
                    if wind_part.endswith(('KT', 'MPS')):
                        return True
    return False


def parse_wind_shear(token: str) -> Optional[WindShear]:
    """
    解析风切变组

    格式：WShhh/wwwddffKT
    - hh: 高度（百英尺），如 020 = 2000 英尺
    - www: 风向（度），如 210 = 210 度
    - dd: 风速（节），如 45 = 45 节
    - ff: 可选阵风

    示例：WS020/21045KT = 2000 英尺高度，风向 210 度，风速 45 节
    """
    if not token.startswith('WS'):
        return None

    remaining = token[2:]

    if '/' not in remaining:
        return None

    parts = remaining.split('/')
    if len(parts) != 2:
        return None

    height_part = parts[0]
    wind_part = parts[1]

    # 解析高度（百英尺）
    if not height_part.isdigit() or len(height_part) != 3:
        return None

    height = int(height_part) * 100  # 转换为英尺

    # 解析单位
    unit = 'MPS'
    if wind_part.endswith('KT'):
        unit = 'KT'
        wind_part = wind_part[:-2]
    elif wind_part.endswith('MPS'):
        wind_part = wind_part[:-3]

    # 解析风向和风速
    # 格式：wwwdd(ff) 或 wwwddGff - 3 位风向 + 2 位风速 + 可选阵风
    # 阵风可能用 G 分隔，如 21045G50 = 风向 210，风速 45，阵风 50
    if len(wind_part) < 5:
        return None

    direction_str = wind_part[:3]
    remaining = wind_part[3:]

    # 检查是否有 G 阵风标记
    gust = None
    if 'G' in remaining:
        speed_str, gust_str = remaining.split('G', 1)
        if gust_str.isdigit():
            gust = int(gust_str)
            if unit == 'KT':
                gust = int(gust * 0.514444)
    else:
        speed_str = remaining

    if not direction_str.isdigit() or not speed_str.isdigit():
        return None

    direction = int(direction_str)
    speed = int(speed_str)

    # 单位转换
    if unit == 'KT':
        speed = int(speed * 0.514444)

    return WindShear(
        height=height,
        direction=direction,
        speed=speed,
        gust=gust
    )


def is_cloud_token(token: str) -> bool:
    """判断是否是云组"""
    cloud_amounts = ('SKC', 'FEW', 'SCT', 'BKN', 'OVC', 'NCD', 'VV')
    return any(token.startswith(amount) for amount in cloud_amounts)


def parse_cloud(token: str) -> Optional[Cloud]:
    """解析云组"""
    cloud_amounts = ('SKC', 'FEW', 'SCT', 'BKN', 'OVC', 'VV')

    for amount in cloud_amounts:
        if token.startswith(amount):
            cloud = Cloud(amount=amount)
            remaining = token[len(amount):]

            # 解析云高（对于 VV，这是垂直能见度）
            if remaining and len(remaining) >= 3:
                # 支持 /// 格式（不明）
                if remaining[:3] == '///':
                    cloud.height = None  # 垂直能见度不明
                    remaining = remaining[3:]
                elif remaining[:3].isdigit():
                    cloud.height = int(remaining[:3]) * 100
                    remaining = remaining[3:]

            # 解析云类型
            if remaining in ('CB', 'TCU'):
                cloud.type = remaining

            return cloud

    return None


def parse_change_group(
    first_token: str,
    token_iter: Iterator[str],
    base_date: datetime,
    valid_from: datetime,
    valid_to: datetime
) -> Tuple[Optional[ChangeGroup], List[str]]:
    """解析变化组（TEMPO/INTER/PROB 等短时预报）"""
    change_type = first_token
    probability = None
    from_time = None
    to_time = None

    remaining_tokens = []

    # 短时预报类型标记
    is_tempo = first_token == 'TEMPO'
    is_inter = first_token == 'INTER'
    prob_value = None

    # 处理 PROBxx 开头（如 PROB30、PROB40）
    if first_token.startswith('PROB') and len(first_token) > 4 and first_token[4:].isdigit():
        prob_value = int(first_token[4:])
        change_type = f'PROB{prob_value}'
        # 检查下一个 token 是否是 TEMPO 或 INTER
        try:
            next_token = next(token_iter)
            if next_token == 'TEMPO':
                change_type = f'PROB{prob_value} TEMPO'
            elif next_token == 'INTER':
                change_type = f'PROB{prob_value} INTER'
            elif '/' in next_token:
                # 直接跟时间格式（如 PROB30 1218/1223），解析时间
                from_time, to_time = parse_ddhhddhh(next_token, base_date)
            else:
                remaining_tokens.append(next_token)
        except StopIteration:
            return None, remaining_tokens
    elif change_type == 'PROB':
        # PROB 后跟概率值的格式
        try:
            prob_token = next(token_iter)
            probability = int(prob_token)
            # 后面通常跟着 TEMPO 或 INTER
            next_token = next(token_iter)
            if next_token in ('TEMPO', 'INTER', 'BECMG'):
                change_type = f'PROB{probability} {next_token}'
            else:
                remaining_tokens.append(next_token)
        except StopIteration:
            return None, remaining_tokens

    # 解析时间
    try:
        # 如果 first_token 是 FM 带时间（如 FM090600），直接解析
        if first_token.startswith('FM') and len(first_token) > 2 and first_token[2:].isdigit():
            # FMDDHHMM 格式
            from_time = parse_ddhhmm(first_token[2:], base_date)
            to_time = valid_to
            change_type = 'FM'  # 规范化为 FM
        elif first_token.startswith('PROB') and len(first_token) > 4 and first_token[4:].isdigit():
            # PROBxx 后跟 TEMPO/INTER 或独立 PROB
            if is_tempo or is_inter or 'TEMPO' in change_type or 'INTER' in change_type:
                time_token = next(token_iter)
                if '/' in time_token:
                    from_time, to_time = parse_ddhhddhh(time_token, base_date)
                else:
                    remaining_tokens.append(time_token)
            else:
                # 独立 PROBxx（不带 TEMPO/INTER）
                time_token = next(token_iter)
                if '/' in time_token:
                    from_time, to_time = parse_ddhhddhh(time_token, base_date)
                else:
                    remaining_tokens.append(time_token)
        elif first_token == 'BECMG':
            # BECMG 可能和 FM/TL/AT 组合
            time_token = next(token_iter)

            if '/' in time_token:
                # DDHH/DDHH - BECMG 标准格式
                from_time, to_time = parse_ddhhddhh(time_token, base_date)

                # 检查后面是否有 FM/TL/AT
                # 注意：如果不是 FM/TL/AT，需要将 token 放回迭代器让 parse_weather_state 处理
                try:
                    next_tok = next(token_iter)
                    if next_tok.startswith('FM') and len(next_tok) > 2 and next_tok[2:].isdigit():
                        change_type = 'BECMG FM'
                        from_time = parse_ddhhmm(next_tok[2:], base_date)
                    elif next_tok.startswith('TL') and len(next_tok) > 2 and next_tok[2:].isdigit():
                        change_type = 'BECMG TL'
                        to_time = parse_ddhhmm(next_tok[2:], base_date)
                    elif next_tok.startswith('AT') and len(next_tok) > 2 and next_tok[2:].isdigit():
                        change_type = 'BECMG AT'
                        from_time = parse_ddhhmm(next_tok[2:], base_date)
                        to_time = from_time
                    else:
                        # 不是 FM/TL/AT，是天气元素，需要放回迭代器让 parse_weather_state 处理
                        # 创建一个新迭代器，先返回这个 token，再返回剩余的
                        def chain_iter(first, rest):
                            yield first
                            yield from rest
                        token_iter = chain_iter(next_tok, token_iter)
                except StopIteration:
                    pass
        else:
            time_token = next(token_iter)

            if time_token.startswith('FM') and len(time_token) > 2 and time_token[2:].isdigit():
                # FMDDHHMM 格式
                from_time = parse_ddhhmm(time_token[2:], base_date)
                to_time = valid_to
                change_type = 'FM'
            elif '/' in time_token:
                # DDHH/DDHH
                from_time, to_time = parse_ddhhddhh(time_token, base_date)
            else:
                # 可能是 FM 格式，再试一次
                remaining_tokens.append(time_token)
    except StopIteration:
        return None, remaining_tokens

    # 解析天气状态
    weather, remaining = parse_weather_state(token_iter, from_time or valid_from, to_time or valid_to)
    remaining_tokens.extend(remaining)

    change_group = ChangeGroup(
        type=change_type,
        probability=probability,
        from_time=from_time,
        to_time=to_time,
        weather=weather
    )

    return change_group, remaining_tokens


def get_weather_at_time(taf: TAF, query_time: datetime) -> WeatherState:
    """
    获取指定时间的天气状态（合并后的结果，兼容旧接口）

    Args:
        taf: 解析后的 TAF 对象
        query_time: 查询时间

    Returns:
        该时间的天气状态（如果 TEMPO 生效，返回合并后的天气）

    Raises:
        ValueError: 当查询时间不在 TAF 有效期内时
    """
    display = get_weather_display_at_time(taf, query_time)
    # 兼容旧接口：如果有 TEMPO，返回合并后的数据
    if display.tempo:
        return _merge_weather(display.main, display.tempo)
    return display.main


def get_weather_display_at_time(taf: TAF, query_time: datetime) -> TAFDisplay:
    """
    获取指定时间的天气显示数据（主体和短时预报分开）

    Args:
        taf: 解析后的 TAF 对象
        query_time: 查询时间

    Returns:
        TAFDisplay 对象，包含主体天气、短时预报明细和最坏情况

    Raises:
        ValueError: 当查询时间不在 TAF 有效期内时
    """
    if query_time < taf.valid_from or query_time > taf.valid_to:
        raise ValueError(
            f"查询时间 {query_time} 不在 TAF 有效期内 "
            f"({taf.valid_from} 至 {taf.valid_to})"
        )

    # 从初始天气开始
    main_weather = deepcopy(taf.initial)

    # 先处理所有 FM 和 BECMG 组（永久性变化）
    # 同时记录生效的 BECMG 组（用于期间取较差值）
    active_becmg_groups = []

    for change in taf.changes:
        if not change.from_time:
            continue

        # FM: 从指定时间起永久改变
        if change.type.startswith('FM'):
            if query_time >= change.from_time:
                main_weather = _merge_weather(main_weather, change.weather)

        # BECMG: 在时间段内逐渐变化
        elif change.type == 'BECMG':
            if query_time >= change.to_time:
                # 变化已完成，应用新天气
                main_weather = _merge_weather(main_weather, change.weather)
            elif query_time >= change.from_time:
                # 变化正在进行中，记录用于取较差值
                active_becmg_groups.append(change)

    # 收集当前时间生效的所有短时预报组
    # 包括：TEMPO, INTER, PROBxx, PROBxx TEMPO, PROBxx INTER, INTER PROBxx
    # 这些类型时间重叠时，取最差值
    short_term_groups = []

    # 处理 BECMG 期间的较差值
    if active_becmg_groups:
        for becmg in active_becmg_groups:
            # 比较主体天气和 BECMG 天气，取较差值
            main_weather = _get_worse_weather(main_weather, becmg.weather)

    SHORT_TERM_TYPES = ('TEMPO', 'INTER', 'PROB')

    for change in taf.changes:
        if not change.from_time or not change.to_time:
            continue

        # 检查是否是短时预报类型
        is_short_term = False
        for st_type in SHORT_TERM_TYPES:
            if st_type in change.type:
                is_short_term = True
                break

        if is_short_term:
            if change.from_time <= query_time < change.to_time:
                short_term_groups.append(change)

    # 生成短时预报明细
    tempo_details = []
    for group in short_term_groups:
        wind_shear_dict = None
        if group.weather.wind and group.weather.wind.wind_shear:
            ws = group.weather.wind.wind_shear
            wind_shear_dict = {
                'height': ws.height,
                'direction': ws.direction,
                'speed': ws.speed,
                'gust': ws.gust
            }

        detail = TEMPODetail(
            time_range=f"{group.from_time.strftime('%H:%M')}-{group.to_time.strftime('%H:%M')}",
            visibility=group.weather.visibility,
            weather=group.weather.weather.copy() if group.weather.weather else [],
            wind_direction=group.weather.wind.direction if group.weather.wind else None,
            wind_speed=group.weather.wind.speed if group.weather.wind else None,
            wind_gust=group.weather.wind.gust if group.weather.wind else None,
            wind_shear=wind_shear_dict,
            clouds=[{'amount': c.amount, 'height': c.height, 'type': c.type} for c in group.weather.clouds]
        )
        tempo_details.append(detail)

    # 如果有多个短时预报，取最差值
    tempo_weather = None
    if short_term_groups:
        tempo_weather = _get_worst_tempo(short_term_groups)

    return TAFDisplay(
        main=main_weather,
        tempo=tempo_weather,
        tempo_details=tempo_details,
        tempo_groups=short_term_groups
    )


def _get_worst_tempo(tempo_groups: List[ChangeGroup]) -> WeatherState:
    """
    从多个 TEMPO 组中取最坏情况

    - 能见度：取最小值
    - 云底高：取最低值（不分云量）
    - 风：取最大值（风速/阵风）
    - 天气现象：按严重程度排序，取最严重的（包含关系去重）
    """
    worst = WeatherState()
    worst.clouds = []
    worst.weather = []

    # 用于找最低云底高
    lowest_cloud_height = None
    lowest_cloud = None
    # 用于记录 VV/// (垂直能见度不明)
    has_vv_unknown = False
    vv_unknown_cloud = None

    for group in tempo_groups:
        tw = group.weather

        # 能见度：取最小值
        if tw.visibility is not None:
            if worst.visibility is None or tw.visibility < worst.visibility:
                worst.visibility = tw.visibility

        # 风：取最大值
        if tw.wind:
            if worst.wind is None:
                worst.wind = deepcopy(tw.wind)
            else:
                # 比较风速
                if tw.wind.speed and (worst.wind.speed is None or tw.wind.speed > worst.wind.speed):
                    worst.wind.speed = tw.wind.speed
                # 比较阵风
                if tw.wind.gust and (worst.wind.gust is None or tw.wind.gust > worst.wind.gust):
                    worst.wind.gust = tw.wind.gust
                # 风向：如果不同，设为可变
                if tw.wind.direction and worst.wind.direction:
                    if tw.wind.direction != worst.wind.direction:
                        worst.wind.variable = True
                elif tw.wind.direction and worst.wind.direction is None:
                    worst.wind.direction = tw.wind.direction

        # 云底高：找最低的云（不分云量类型）
        if tw.clouds:
            for cloud in tw.clouds:
                # 特殊处理 VV/// (垂直能见度不明)
                if cloud.amount == 'VV' and cloud.height is None:
                    has_vv_unknown = True
                    vv_unknown_cloud = deepcopy(cloud)
                elif cloud.height is not None:
                    if lowest_cloud_height is None or cloud.height < lowest_cloud_height:
                        lowest_cloud_height = cloud.height
                        lowest_cloud = deepcopy(cloud)

        # 天气现象：收集所有
        if tw.weather:
            for w in tw.weather:
                if w not in worst.weather:
                    worst.weather.append(w)

    # 将最低的云或 VV/// 添加到结果中
    # 优先显示 VV/// (垂直能见度不明是最严重的情况)
    if vv_unknown_cloud:
        worst.clouds = [vv_unknown_cloud]
    elif lowest_cloud:
        worst.clouds = [lowest_cloud]

    # 天气现象：按严重程度排序并去重
    worst.weather = _merge_weather_phenomena(worst.weather)

    return worst


def _merge_weather_phenomena(weather_list: List[str]) -> List[str]:
    """
    合并天气现象，按严重程度排序并去重

    严重程度评分（越高越严重）：
    - 雷暴 (TS) + 降水：最严重
    - 冰雹 (GR)：非常严重
    - 阵性降水 (SH)：较严重
    - 沙暴/尘暴 (SS/DS)：严重
    - 雾 (FG)：严重影响能见度
    - 降水 (RA/SN 等)：中等
    - 轻雾/霾 (BR/HZ)：较轻
    """
    if not weather_list:
        return []

    # 天气现象严重程度评分
    severity_scores = {
        # 雷暴类（最严重）
        'TSRA': 90, 'TSSN': 85, 'TS': 80, 'TSPL': 88, 'TSGR': 95, 'TSGS': 92,
        # 冻雨（非常严重，仅次于冰雹）
        'FZRA': 78, 'FZDZ': 76,
        # 冰雹
        'GR': 75, 'GS': 70, 'PL': 65, 'IC': 60,
        # 沙暴/尘暴（提升到最高优先级）
        'SS': 88, 'DS': 86,
        # 阵性降水
        'SHRA': 55, 'SHSN': 52, 'SHGR': 58, 'SHGS': 56, 'SH': 50,
        # 雾类（影响能见度）
        'FG': 60, 'VCFG': 55, 'MIFG': 50, 'BCFG': 48,
        # 降水类（提升到阵性降水前面）
        'RA': 62, 'SN': 61, 'DZ': 58, 'SG': 57, 'PE': 59,
        # 视程障碍
        'FU': 45, 'VA': 48, 'DU': 35, 'SA': 38, 'HZ': 32, 'BR': 25,
        # 其他
        'SQ': 60, 'FC': 65, 'PO': 55,
        # 高吹/低吹
        'DRSA': 40, 'DRDU': 38, 'DRSN': 42,
        # 高吹沙/尘（比低吹严重）
        'BLSA': 55, 'BLDU': 53, 'BLPY': 50,
    }

    # 去重处理：如果存在包含关系，保留更严重的
    # TSRA 包含 RA，TSSN 包含 SN 等
    simplified = []
    for w in weather_list:
        # 检查是否已被更严重的包含
        is_superseded = False
        for existing in simplified:
            if _is_weather_superseded(w, existing):
                is_superseded = True
                break
            if _is_weather_superseded(existing, w):
                simplified.remove(existing)
        if not is_superseded:
            simplified.append(w)

    # 按严重程度排序
    simplified.sort(key=lambda x: severity_scores.get(x, 50), reverse=True)

    # 只保留最严重的前 3 个（避免显示过多）
    return simplified[:3]


def _is_weather_superseded(w1: str, w2: str) -> bool:
    """
    判断 w1 是否被 w2 包含（即 w2 更严重/更全面）

    例如：RA 被 TSRA 包含，SN 被 TSSN 包含，SHRA 被 TSRA 包含
    """
    # 去除强度前缀进行比较
    w1_code = w1.lstrip('+-')
    w2_code = w2.lstrip('+-')

    # 雷暴 (TS) 包含所有阵性降水 (SH) 和普通降水
    if w2_code.startswith('TS') and not w1_code.startswith('TS'):
        # TSRA 包含 RA, SHRA; TSSN 包含 SN, SHSN; 等
        w2_base = w2_code[2:] if len(w2_code) > 2 else ''
        w1_base = w1_code[2:] if w1_code.startswith('SH') else w1_code
        if w1_code.startswith('SH'):
            # SHRA 被 TSRA 包含
            if w2_base == w1_base or (not w2_base and w1_base in ['RA', 'SN', 'GR', 'GS', 'PL', 'DZ']):
                return True
        elif w2_base == w1_code or (not w2_base and w1_code in ['RA', 'SN', 'GR', 'GS', 'PL', 'DZ']):
            return True
        # TS 单独出现时包含所有降水
        if not w2_base and w1_code in ['RA', 'SN', 'GR', 'GS', 'PL', 'DZ', 'SHRA', 'SHSN']:
            return True

    # 阵性降水 (SH) 包含普通降水
    if w2_code.startswith('SH') and not w1_code.startswith('SH') and not w1_code.startswith('TS'):
        w2_base = w2_code[2:]
        if w2_base == w1_code:
            return True

    # 冻雨 (FZ) 包含普通降水
    if w2_code.startswith('FZ') and not w1_code.startswith('FZ') and not w1_code.startswith('TS'):
        w2_base = w2_code[2:]
        if w2_base == w1_code:
            return True
        # FZRA 包含 RA，FZDZ 包含 DZ
        if w2_code == 'FZRA' and w1_code == 'RA':
            return True
        if w2_code == 'FZDZ' and w1_code == 'DZ':
            return True

    # 强度前缀：+RA 比 RA 严重，-RA 比 RA 轻
    if w1.lstrip('+-') == w2.lstrip('+-'):
        if w1.startswith('-') and not w2.startswith('-'):
            return True
        if not w1.startswith('+') and w2.startswith('+'):
            return True

    # 吹雪/高吹雪：BLSN 包含 DRSN（吹雪比低吹雪严重）
    bl_map = {'BLSA': ['DRSA'], 'BLDU': ['DRDU'], 'BLSN': ['DRSN'], 'BLPY': []}
    if w2_code in bl_map and w1_code in bl_map[w2_code]:
        return True

    # 雾：FG 包含 MIFG/BCFG/PRFG 等
    if w2_code == 'FG' and w1_code in ['MIFG', 'BCFG', 'PRFG', 'VCFG']:
        return True

    return False


def _merge_weather(base: WeatherState, change: WeatherState) -> WeatherState:
    """合并天气状态，用变化覆盖基础"""
    merged = deepcopy(base)

    # 风
    if change.wind:
        merged.wind = change.wind

    # 能见度和 CAVOK
    if change.cavok:
        merged.cavok = True
        merged.visibility = 10000
        merged.weather = []
        merged.clouds = []
    elif change.visibility is not None:
        merged.visibility = change.visibility
        merged.cavok = False

    # 天气现象（如果有新的，替换旧的）
    if change.weather:
        if 'NSW' in change.weather:
            # NSW 表示无重要天气，清除所有天气现象
            merged.weather = []
        else:
            merged.weather = change.weather

    # 云（如果有新的，替换旧的）
    if change.clouds:
        merged.clouds = change.clouds

    return merged


def _get_worse_weather(base: WeatherState, change: WeatherState) -> WeatherState:
    """
    比较两个天气状态，返回较差值（用于 BECMG 期间）

    较差值定义：
    - 能见度：取较小值
    - 风速：取较大值
    - 阵风：取较大值
    - 云底高：取较低值
    - 天气现象：合并并按严重程度排序

    Args:
        base: 基础天气状态（变化前）
        change: 变化后的天气状态

    Returns:
        较差的天气状态
    """
    from copy import deepcopy

    worst = deepcopy(base)

    # 能见度：取较小值（更差）
    if change.visibility is not None:
        if worst.visibility is None or change.visibility < worst.visibility:
            worst.visibility = change.visibility

    # CAVOK：如果变化是 CAVOK，表示天气良好，不是变差
    # 所以 base 不是 CAVOK 时，不应用 CAVOK

    # 风：取较大值（更差）
    if change.wind:
        if worst.wind is None:
            worst.wind = deepcopy(change.wind)
        else:
            # 比较风速
            if change.wind.speed and (worst.wind.speed is None or change.wind.speed > worst.wind.speed):
                worst.wind.speed = change.wind.speed
            # 比较阵风
            if change.wind.gust and (worst.wind.gust is None or change.wind.gust > worst.wind.gust):
                worst.wind.gust = change.wind.gust
            # 风向：如果变化是 VRB（可变风向），优先使用 VRB
            if change.wind.variable:
                worst.wind.variable = True
                worst.wind.direction = None  # VRB 时清空具体风向
            elif change.wind.direction and worst.wind.direction:
                if change.wind.direction != worst.wind.direction:
                    worst.wind.variable = True
            elif change.wind.direction and worst.wind.direction is None:
                worst.wind.direction = change.wind.direction

    # 云底高：取较低值（更差）
    if change.clouds:
        # 找到 change 中最低的云
        lowest_change_cloud = None
        lowest_change_height = None
        has_vv_unknown = False
        vv_unknown_cloud = None

        for cloud in change.clouds:
            if cloud.amount == 'VV' and cloud.height is None:
                has_vv_unknown = True
                vv_unknown_cloud = deepcopy(cloud)
            elif cloud.height is not None:
                if lowest_change_height is None or cloud.height < lowest_change_height:
                    lowest_change_height = cloud.height
                    lowest_change_cloud = deepcopy(cloud)

        # 找到 base 中最低的云
        lowest_base_cloud = None
        lowest_base_height = None
        base_has_vv_unknown = False

        for cloud in worst.clouds:
            if cloud.amount == 'VV' and cloud.height is None:
                base_has_vv_unknown = True
            elif cloud.height is not None:
                if lowest_base_height is None or cloud.height < lowest_base_height:
                    lowest_base_height = cloud.height
                    lowest_base_cloud = deepcopy(cloud)

        # 比较并取最低值（VV/// 最严重）
        if has_vv_unknown or base_has_vv_unknown:
            if vv_unknown_cloud:
                worst.clouds = [vv_unknown_cloud]
            else:
                worst.clouds = [Cloud(amount='VV', height=None)]
        elif lowest_change_cloud:
            if lowest_base_cloud is None or lowest_change_cloud.height < lowest_base_cloud.height:
                worst.clouds = [lowest_change_cloud]
            # 否则保留 base 的云

    # 天气现象：处理 NSW 和合并
    if 'NSW' in change.weather:
        # NSW 表示无重要天气，清除所有天气现象
        worst.weather = []
    elif change.weather:
        # 合并天气现象并按严重程度排序
        all_weather = worst.weather + change.weather
        worst.weather = _merge_weather_phenomena(all_weather)

    return worst


def batch_parse(input_dir: str, output_dir: str) -> None:
    """
    批量解析 TAF 文件

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
    """
    import os
    import json
    from pathlib import Path

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for file_path in input_path.glob('*.taf'):
        with open(file_path, 'r', encoding='utf-8') as f:
            taf_text = f.read()

        try:
            taf = parse_taf(taf_text)
            output_file = output_path / f'{file_path.stem}.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(taf.model_dump(mode='json'), f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"解析 {file_path} 失败：{e}")
