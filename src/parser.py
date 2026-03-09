"""
TAF 解析器核心逻辑
"""

import re
from datetime import datetime
from typing import Optional, List, Iterator, Tuple
from copy import deepcopy

try:
    from .models import TAF, WeatherState, ChangeGroup, Wind, Cloud
    from .utils import parse_ddhhmm, parse_ddhhddhh
except ImportError:
    from models import TAF, WeatherState, ChangeGroup, Wind, Cloud
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
        # 移除 TAF 开头标记
        line = re.sub(r'^TAF\s+', '', line, flags=re.IGNORECASE)
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
        raise TAFParseError(f"无效的 ICAO 代码: {icao}")

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
        if token in ('FM', 'BECMG', 'TEMPO', 'PROB', 'INTER'):
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
    """解析发布时间，格式 DDHHMMZ"""
    if not time_str.endswith('Z'):
        raise TAFParseError(f"发布时间格式错误，应以 Z 结尾: {time_str}")
    return parse_ddhhmm(time_str[:-1])


def parse_validity(validity_str: str, base_date: datetime) -> Tuple[datetime, datetime]:
    """解析有效期，格式 DDHH/DDHH"""
    try:
        return parse_ddhhddhh(validity_str, base_date)
    except Exception as e:
        raise TAFParseError(f"无效的有效期格式: {validity_str}") from e


def parse_weather_state(
    token_iter: Iterator[str],
    period_start: datetime,
    period_end: datetime
) -> Tuple[WeatherState, List[str]]:
    """
    解析天气状态

    Returns:
        (WeatherState, 剩余的tokens)
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
            # 收集剩余所有token
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
                weather.visibility = int(token)
            visibility_parsed = True
            continue

        # CAVOK 也需要单独处理
        if token == 'CAVOK':
            weather.cavok = True
            weather.visibility = 10000
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

        # 未知token，可能是变化组的一部分，保存起来
        remaining.append(token)

    return weather, remaining


def is_wind_token(token: str) -> bool:
    """判断是否是风组"""
    # 格式: dddffMPS, dddffGffMPS, VRBffMPS, 或 KT 结尾
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
        # 前3位是风向，后2位是风速
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
    """判断是否是能见度或CAVOK"""
    if token == 'CAVOK':
        return True
    if token.isdigit() and len(token) <= 4:
        return True
    return False


def is_weather_token(token: str) -> bool:
    """判断是否是天气现象"""
    # 天气现象通常是2-9个字符，由特定的代码组成
    weather_prefixes = ('-', '+', 'VC', 'RE', 'MI', 'PR', 'BC', 'DR', 'BL', 'SH', 'TS', 'FZ')
    weather_codes = ('DZ', 'RA', 'SN', 'SG', 'IC', 'PL', 'GR', 'GS', 'UP',
                     'BR', 'FG', 'FU', 'VA', 'DU', 'SA', 'HZ',
                     'PO', 'SQ', 'FC', 'SS', 'DS', 'NSW')

    # 移除强度前缀
    test_token = token
    if test_token.startswith(('+', '-')):
        test_token = test_token[1:]

    # 检查是否包含天气代码
    for code in weather_codes:
        if code in test_token:
            return True
    for prefix in weather_prefixes:
        if test_token.startswith(prefix):
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
    if change_type == 'PROB':
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
        time_token = next(token_iter)

        if change_type.startswith('FM'):
            # FMDDHHMM
            from_time = parse_ddhhmm(time_token[2:] if time_token.startswith('FM') else time_token, base_date)
            to_time = valid_to
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
    获取指定时间的天气状态

    Args:
        taf: 解析后的 TAF 对象
        query_time: 查询时间

    Returns:
        该时间的天气状态

    Raises:
        ValueError: 当查询时间不在 TAF 有效期内时
    """
    if query_time < taf.valid_from or query_time > taf.valid_to:
        raise ValueError(
            f"查询时间 {query_time} 不在 TAF 有效期内 "
            f"({taf.valid_from} 至 {taf.valid_to})"
        )

    # 从初始天气开始
    current_weather = deepcopy(taf.initial)

    # 先处理所有 FM 和 BECMG 组（永久性变化）
    for change in taf.changes:
        if not change.from_time:
            continue

        # FM: 从指定时间起永久改变
        if change.type.startswith('FM'):
            if query_time >= change.from_time:
                current_weather = _merge_weather(current_weather, change.weather)

        # BECMG: 在时间段内逐渐变化，查询时间在结束时间后完全生效
        elif change.type == 'BECMG':
            if query_time >= change.to_time:
                current_weather = _merge_weather(current_weather, change.weather)

    # 再检查是否有 TEMPO 组在当前时间生效（暂时性变化）
    for change in taf.changes:
        if not change.from_time or not change.to_time:
            continue

        # TEMPO/PROB: 只在时间段内暂时有效
        if 'TEMPO' in change.type:
            if change.from_time <= query_time < change.to_time:
                # 对于 TEMPO，返回合并后的天气
                temp_weather = _merge_weather(current_weather, change.weather)
                return temp_weather

    return current_weather


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
            print(f"解析 {file_path} 失败: {e}")
