"""枚举工具函数，提供安全的枚举值访问"""

from enum import Enum
from typing import Any, Optional, Union


def safe_enum_value(enum_obj: Any, default: Any = None) -> Any:
    """
    安全获取枚举值，处理枚举对象和字符串的情况

    Args:
        enum_obj: 可能是枚举对象或字符串
        default: 默认值，当无法获取值时返回

    Returns:
        枚举的value属性或字符串本身，或默认值
    """
    if enum_obj is None:
        return default

    # 如果是枚举对象，返回其value
    if isinstance(enum_obj, Enum):
        return enum_obj.value

    # 如果有value属性，返回value
    if hasattr(enum_obj, "value"):
        return enum_obj.value

    # 如果是字符串，直接返回
    if isinstance(enum_obj, str):
        return enum_obj

    # 其他情况返回默认值
    return default


def safe_enum_name(enum_obj: Any, default: Any = None) -> Any:
    """
    安全获取枚举名称

    Args:
        enum_obj: 可能是枚举对象或字符串
        default: 默认值

    Returns:
        枚举的name属性或对象本身，或默认值
    """
    if enum_obj is None:
        return default

    # 如果是枚举对象，返回其name
    if isinstance(enum_obj, Enum):
        return enum_obj.name

    # 如果有name属性，返回name
    if hasattr(enum_obj, "name"):
        return enum_obj.name

    # 如果是字符串，直接返回
    if isinstance(enum_obj, str):
        return enum_obj

    # 其他情况返回默认值
    return default
