"""
工具函数
"""

from datetime import datetime, timedelta
from typing import Optional


def parse_ddhhmm(ddhhmm_str: str, base_date: Optional[datetime] = None) -> datetime:
    """
    解析日期时间格式 DDHHMM

    Args:
        ddhhmm_str: "DDHHMM" 格式字符串
        base_date: 基准日期，用于推算月份和年份

    Returns:
        datetime 对象
    """
    if base_date is None:
        base_date = datetime.utcnow()

    day = int(ddhhmm_str[0:2])
    hour = int(ddhhmm_str[2:4])
    minute = int(ddhhmm_str[4:6])

    # 处理跨月情况
    result = base_date.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)

    # 如果日号小于当前日，认为是下个月
    if day < base_date.day:
        if result.month == 12:
            result = result.replace(year=result.year + 1, month=1)
        else:
            result = result.replace(month=result.month + 1)

    return result


def parse_ddhhddhh(ddhhddhh_str: str, base_date: Optional[datetime] = None) -> tuple:
    """
    解析时间段格式 DDHH/DDHH

    Args:
        ddhhddhh_str: "DDHH/DDHH" 格式字符串
        base_date: 基准日期

    Returns:
        (from_datetime, to_datetime)
    """
    from_str, to_str = ddhhddhh_str.split('/')
    from_dt = parse_ddhhmm(from_str + "00", base_date)
    to_dt = parse_ddhhmm(to_str + "00", base_date)
    return from_dt, to_dt


def meters_to_statute_miles(meters: int) -> float:
    """米转换为 statute miles"""
    return meters * 0.000621371


def mps_to_knots(mps: int) -> float:
    """米/秒转换为节"""
    return mps * 1.943844


WEATHER_CODES_CN = {
    "RA": "雨",
    "DZ": "毛毛雨",
    "SN": "雪",
    "SG": "米雪",
    "IC": "冰晶",
    "PL": "冰粒",
    "GR": "冰雹",
    "GS": "小冰雹/雪粒",
    "BR": "轻雾",
    "FG": "雾",
    "FU": "烟",
    "VA": "火山灰",
    "DU": "浮尘",
    "SA": "沙",
    "HZ": "霾",
    "PO": "尘/沙旋风",
    "SQ": "飑",
    "FC": "漏斗云",
    "SS": "沙暴",
    "DS": "尘暴",
    "TS": "雷暴",
    "SH": "阵",
    "FZ": "冻",
    "MI": "浅",
    "PR": "部分",
    "BC": "补丁",
    "DR": "低吹",
    "BL": "高吹",
    "VC": "附近",
    "RE": "近来",
    "NSW": "无重要天气",
}


def weather_code_to_cn(code: str) -> str:
    """天气代码转中文"""
    if code == 'NSW':
        return '无重要天气'

    # 处理常见组合
    special_cases = {
        'TSRA': '雷暴伴雨',
        'SHRA': '阵雨',
        'SHSN': '阵雪',
        'FZRA': '冻雨',
        'FZDZ': '冻毛毛雨',
        'TS': '雷暴',
        'BR': '轻雾',
        'FG': '雾',
        'RA': '雨',
        'SN': '雪',
        'DZ': '毛毛雨',
    }

    # 处理前缀
    prefix = ""
    if code.startswith("+"):
        prefix = "强"
        code = code[1:]
    elif code.startswith("-"):
        prefix = "小"
        code = code[1:]

    # 检查特殊组合
    if code in special_cases:
        return prefix + special_cases[code]

    # 通用解析
    result = []
    i = 0
    while i < len(code):
        # 先尝试匹配2字符
        matched = False
        if i + 1 < len(code):
            two_char = code[i:i+2]
            if two_char in WEATHER_CODES_CN:
                result.append(WEATHER_CODES_CN[two_char])
                i += 2
                matched = True
        if not matched:
            # 尝试匹配1字符
            one_char = code[i]
            if one_char in WEATHER_CODES_CN:
                result.append(WEATHER_CODES_CN[one_char])
            i += 1

    return prefix + "".join(result)


CLOUD_AMOUNT_CN = {
    "SKC": "晴空",
    "FEW": "少云",
    "SCT": "疏云",
    "BKN": "多云",
    "OVC": "阴天",
}


def cloud_amount_to_cn(amount: str) -> str:
    """云量转中文"""
    return CLOUD_AMOUNT_CN.get(amount, amount)
