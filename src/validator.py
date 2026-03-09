"""
TAF 数据验证器
"""

from .models import TAF


class TAFValidationError(Exception):
    """TAF 验证错误"""
    pass


def validate_taf(taf: TAF) -> bool:
    """
    验证 TAF 数据完整性

    Args:
        taf: TAF 对象

    Returns:
        验证是否通过

    Raises:
        TAFValidationError: 验证失败时抛出
    """
    errors = []

    # 验证 ICAO 代码
    if len(taf.icao) != 4:
        errors.append(f"ICAO 代码应为4个字符: {taf.icao}")

    # 验证时间
    if taf.valid_from >= taf.valid_to:
        errors.append("有效开始时间必须早于结束时间")

    # 验证能见度
    if taf.initial.visibility is not None:
        if taf.initial.visibility < 0:
            errors.append("能见度不能为负数")

    if errors:
        raise TAFValidationError("; ".join(errors))

    return True
