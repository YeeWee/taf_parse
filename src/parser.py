"""
TAF 解析器核心逻辑
"""

import re
from datetime import datetime
from typing import Optional, List, Iterator, Tuple
from copy import deepcopy

try:
    from .models import TAF, WeatherState, ChangeGroup, Wind, Cloud, TAFDisplay, TEMPODetail
    from .utils import parse_ddhhmm, parse_ddhhddhh
except ImportError:
    from models import TAF, WeatherState, ChangeGroup, Wind, Cloud, TAFDisplay, TEMPODetail
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
        # 移除 WMO 报头（如 FTUS31 KWBC 071740）
        # WMO 报头格式：行号 + 发报中心 + 时间，后面跟着 TAF
        # 例如：FTUS31 KWBC 071740 TAF ...
        # 方法：匹配 TAF 之前的所有内容和 TAF 标记本身
        line = re.sub(r'^.*?\s+(?=TAF\s)', '', line, flags=re.IGNORECASE)

        # 移除 TAF 开头标记（包括 TAF AMD 修订报、TAF COR 更正报）
        # 根据《民用航空气象报文规范》附录二 2.1
        line = re.sub(r'^TAF\s+(AMD\s+|COR\s+)?', '', line, flags=re.IGNORECASE)
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
        if token in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER'):
            pass  # 标准格式
        elif token.startswith('FM') and len(token) > 2 and token[2:].isdigit():
            change_type = 'FM'  # FMDDHHMM 格式
        elif token.startswith('PROB') and len(token) > 4 and token[4:].isdigit():
            change_type = 'PROB'  # PROB30、PROB40 等格式
        else:
            change_type = None

        if change_type in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER'):
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
    if not time_str.endswith('Z'):
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

    for token in token_iter:
        # 检查是否遇到变化组开始标记
        if token in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER', 'TX', 'TN'):
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(list(token_iter))
            break
        # 检查是否是 PROB 带概率（如 PROB30、PROB40）
        if token.startswith('PROB') and len(token) > 4 and token[4:].isdigit():
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(list(token_iter))
            break

        # 检查是否是 FM 开头带时间的标记（如 FM090600）
        if token.startswith('FM') and len(token) > 2 and token[2:].isdigit():
            remaining.append(token)
            # 收集剩余所有 token
            remaining.extend(list(token_iter))
            break

        # 检查是否遇到备注标记，跳过后续内容
        if token in ('RMK', 'NXT', 'FCST', 'BY'):
            # 跳过备注部分
            remaining.extend(list(token_iter))
            break

        # 尝试解析风
        if not wind_parsed and is_wind_token(token):
            weather.wind = parse_wind(token)
            wind_parsed = True
            continue

        # 尝试解析能见度
        if not visibility_parsed and is_visibility_token(token):
            if token == 'CAVOK':
                weather.cavok = True
                weather.visibility = 10000
            else:
                vis = parse_visibility(token)
                if vis is not None:
                    weather.visibility = vis
            visibility_parsed = True
            continue

        # 尝试解析天气现象
        if is_weather_token(token):
            weather.weather.append(token)
            continue

        # 尝试解析云
        if is_cloud_token(token):
            cloud = parse_cloud(token)
            if cloud:
                weather.clouds.append(cloud)
            continue

        # NSW - No Significant Weather
        if token == 'NSW':
            weather.weather = []
            continue

        # NCD - No Cloud Detected
        if token == 'NCD':
            weather.clouds = []
            continue

        # 未知 token，可能是变化组的一部分，保存起来
        remaining.append(token)

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
        wind.gust = int(gust_match.group(1))
        token = token[:gust_match.start()] + token[gust_match.end():]

    # 解析风向和风速
    if token.startswith('VRB'):
        wind.variable = True
        speed_str = token[3:]
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
    # 米制：纯数字，如 6000、1500
    if token.isdigit() and len(token) <= 4:
        return True
    # 英制：如 P6SM、5SM、1/2SM、3/4SM 等
    if token.endswith('SM'):
        return True
    return False


def parse_visibility(token: str) -> Optional[int]:
    """
    解析能见度，返回米

    Args:
        token: 能见度 token，如 '6000'、'P6SM'、'5SM'、'1/2SM'

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


def is_cloud_token(token: str) -> bool:
    """判断是否是云组"""
    cloud_amounts = ('SKC', 'FEW', 'SCT', 'BKN', 'OVC', 'NCD')
    return any(token.startswith(amount) for amount in cloud_amounts)


def parse_cloud(token: str) -> Optional[Cloud]:
    """解析云组"""
    cloud_amounts = ('SKC', 'FEW', 'SCT', 'BKN', 'OVC')

    for amount in cloud_amounts:
        if token.startswith(amount):
            cloud = Cloud(amount=amount)
            remaining = token[len(amount):]

            # 解析云高
            if remaining and len(remaining) >= 3 and remaining[:3].isdigit():
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
    """解析变化组"""
    change_type = first_token
    probability = None
    from_time = None
    to_time = None

    remaining_tokens = []

    # 处理 PROB
    # 检查是否是 PROB30 这种格式（first_token 就是 PROB30）
    if first_token.startswith('PROB') and len(first_token) > 4 and first_token[4:].isdigit():
        probability = int(first_token[4:])
        change_type = f'PROB{probability}'
        # 继续解析时间和天气
    elif change_type == 'PROB':
        try:
            prob_token = next(token_iter)
            probability = int(prob_token)
            # 后面通常跟着 TEMPO
            next_token = next(token_iter)
            if next_token in ('TEMPO', 'BECMG'):
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
            # PROB30 格式，时间下一个 token
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
                        remaining_tokens.append(next_tok)
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
    获取指定时间的天气显示数据（主体和 TEMPO 分开）

    Args:
        taf: 解析后的 TAF 对象
        query_time: 查询时间

    Returns:
        TAFDisplay 对象，包含主体天气、TEMPO 明细和最坏情况

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
    for change in taf.changes:
        if not change.from_time:
            continue

        # FM: 从指定时间起永久改变
        if change.type.startswith('FM'):
            if query_time >= change.from_time:
                main_weather = _merge_weather(main_weather, change.weather)

        # BECMG: 在时间段内逐渐变化，查询时间在结束时间后完全生效
        elif change.type == 'BECMG':
            if query_time >= change.to_time:
                main_weather = _merge_weather(main_weather, change.weather)

    # 收集当前时间生效的所有 TEMPO 组（包括 PROB）
    active_tempo_groups = []
    for change in taf.changes:
        if not change.from_time or not change.to_time:
            continue

        # TEMPO/PROB: 只在时间段内暂时有效
        # PROB30、PROB40 等概率组也视为 TEMPO 类型
        if 'TEMPO' in change.type or change.type.startswith('PROB'):
            if change.from_time <= query_time < change.to_time:
                active_tempo_groups.append(change)

    # 生成 TEMPO 明细
    tempo_details = []
    for group in active_tempo_groups:
        detail = TEMPODetail(
            time_range=f"{group.from_time.strftime('%H:%M')}-{group.to_time.strftime('%H:%M')}",
            visibility=group.weather.visibility,
            weather=group.weather.weather.copy() if group.weather.weather else [],
            wind_direction=group.weather.wind.direction if group.weather.wind else None,
            wind_speed=group.weather.wind.speed if group.weather.wind else None,
            wind_gust=group.weather.wind.gust if group.weather.wind else None,
            clouds=[{'amount': c.amount, 'height': c.height, 'type': c.type} for c in group.weather.clouds]
        )
        tempo_details.append(detail)

    # 如果有多个 TEMPO，取最差值
    tempo_weather = None
    if active_tempo_groups:
        tempo_weather = _get_worst_tempo(active_tempo_groups)

    return TAFDisplay(
        main=main_weather,
        tempo=tempo_weather,
        tempo_details=tempo_details,
        tempo_groups=active_tempo_groups
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
                if cloud.height is not None:
                    if lowest_cloud_height is None or cloud.height < lowest_cloud_height:
                        lowest_cloud_height = cloud.height
                        lowest_cloud = deepcopy(cloud)

        # 天气现象：收集所有
        if tw.weather:
            for w in tw.weather:
                if w not in worst.weather:
                    worst.weather.append(w)

    # 将最低的云添加到结果中
    if lowest_cloud:
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
        merged.weather = change.weather

    # 云（如果有新的，替换旧的）
    if change.clouds:
        merged.clouds = change.clouds

    return merged


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
