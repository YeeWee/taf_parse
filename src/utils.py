"""
工具函数
"""

from datetime import datetime, timedelta
from typing import Optional


def parse_ddhhmm(ddhhmm_str: str, base_date: Optional[datetime] = None) -> datetime:
    """
    解析日期时间格式 DDHHMM

    Args:
        ddhhmm_str: "DDHHMM" 格式字符串，HH 可以是 00-24
        base_date: 基准日期，用于推算月份和年份。如果为 None，使用当前日期

    Returns:
        datetime 对象
    """
    if base_date is None:
        base_date = datetime.utcnow()

    day = int(ddhhmm_str[0:2])
    hour = int(ddhhmm_str[2:4])
    minute = int(ddhhmm_str[4:6])

    # 处理 24 时（日界）- 24:00 即次日 00:00
    if hour == 24:
        hour = 0
        day += 1

    # 处理跨月情况：根据基准日期确定月份
    result = base_date.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)

    # 如果日号小于基准日号，且相差较大，可能是下个月
    # 例如：基准日期是 31 日，解析 01 日，应该是下月 1 日
    if day < base_date.day and base_date.day - day >= 25:
        # 日号差值大，认为是下个月
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
    # 降水类
    "DZ": "毛毛雨",
    "RA": "雨",
    "SN": "雪",
    "SG": "米雪",
    "IC": "冰晶",
    "PL": "冰粒",
    "GR": "冰雹",
    "GS": "小冰雹/雪粒",
    # 视程障碍现象类
    "FG": "雾",
    "BR": "轻雾",
    "FU": "烟",
    "VA": "火山灰",
    "DU": "浮尘",
    "SA": "沙",
    "HZ": "霾",
    # 其他类
    "PO": "尘/沙卷风",
    "SQ": "飑",
    "FC": "漏斗云",
    "SS": "沙暴",
    "DS": "尘暴",
    # 特征描述
    "TS": "雷暴",
    "SH": "阵",
    "FZ": "冻",
    "MI": "浅",
    "PR": "部分",
    "BC": "碎片",
    "DR": "低吹",
    "BL": "高吹",
    "VC": "附近",
    "RE": "近来",
    # 其他
    "NSW": "无重要天气",
    "UP": "不明降水",
}


def weather_code_to_cn(code: str) -> str:
    """
    天气代码转中文

    根据《民用航空气象报文规范》规定的天气现象强度、特征及类型进行解析：
    - 强度：+ (强)、- (小/弱)、无符号 (中)
    - 特征：TS(雷暴)、FZ(冻结)、SH(阵性)、BL(高吹)、DR(低吹)、MI(浅)、BC(碎片)、PR(部分)
    - 类型：降水类、视程障碍类、其他类
    """
    if code == 'NSW':
        return '无重要天气'

    # 处理常见组合（按文档规范的组合顺序）
    special_cases = {
        # 雷暴组合
        'TSRA': '雷暴伴雨',
        'TSSN': '雷暴伴雪',
        'TSGR': '雷暴伴冰雹',
        'TSGS': '雷暴伴小冰雹',
        'TSPL': '雷暴伴冰粒',
        'TSSG': '雷暴伴米雪',
        # 阵性组合
        'SHRA': '阵雨',
        'SHSN': '阵雪',
        'SHGR': '阵性冰雹',
        'SHGS': '阵性小冰雹',
        'SHPL': '阵性冰粒',
        # 冻结组合
        'FZRA': '冻雨',
        'FZDZ': '冻毛毛雨',
        'FZFG': '冻雾',
        # 低吹组合
        'DRSA': '低吹沙',
        'DRDU': '低吹尘',
        'DRSN': '低吹雪',
        # 高吹组合
        'BLSA': '高吹沙',
        'BLDU': '高吹尘',
        'BLSN': '高吹雪',
        # 雾组合
        'MIFG': '浅雾',
        'BCFG': '碎片雾',
        'PRFG': '部分雾',
        # 单独代码
        'TS': '雷暴',
        'BR': '轻雾',
        'FG': '雾',
        'RA': '雨',
        'SN': '雪',
        'DZ': '毛毛雨',
        'GR': '冰雹',
        'GS': '小冰雹',
        'PL': '冰粒',
        'SG': '米雪',
        'IC': '冰晶',
        'UP': '不明降水',
        'SA': '沙',
        'DU': '尘',
        'HZ': '霾',
        'FU': '烟',
        'VA': '火山灰',
        'PO': '尘/沙卷风',
        'SQ': '飑',
        'FC': '漏斗云',
        'SS': '沙暴',
        'DS': '尘暴',
    }

    # 处理前缀（强度）
    prefix = ""
    if code.startswith("+"):
        prefix = "强"
        code = code[1:]
    elif code.startswith("-"):
        prefix = "小"
        code = code[1:]

    # 处理前缀（特征/位置）
    feature_prefix = ""
    if code.startswith('VC'):
        feature_prefix = "附近"
        code = code[2:]
    elif code.startswith('RE'):
        feature_prefix = "近来"
        code = code[2:]

    # 检查特殊组合
    if code in special_cases:
        return prefix + feature_prefix + special_cases[code]

    # 通用解析 - 按文档规范的顺序：特征 + 类型
    result = []
    i = 0
    while i < len(code):
        matched = False
        # 先尝试匹配 2 字符（特征代码）
        if i + 1 < len(code):
            two_char = code[i:i+2]
            if two_char in WEATHER_CODES_CN:
                result.append(WEATHER_CODES_CN[two_char])
                i += 2
                matched = True
        if not matched:
            # 尝试匹配 1 字符（类型代码）
            one_char = code[i:i+1]
            if one_char in WEATHER_CODES_CN:
                result.append(WEATHER_CODES_CN[one_char])
            i += 1

    weather_text = "".join(result)
    return prefix + feature_prefix + weather_text


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
