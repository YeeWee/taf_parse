"""
TAF Parse - 机场天气预报解析器

一个用于解析航空 TAF (Terminal Aerodrome Forecast) 气象报文的 Python 库。
"""

__version__ = "0.2.0"
__author__ = "Wee"

from .parser import parse_taf, get_weather_at_time, batch_parse
from .models import TAF, WeatherState, ChangeGroup, Wind, Cloud
from .utils import weather_code_to_cn, cloud_amount_to_cn

__all__ = [
    "parse_taf",
    "get_weather_at_time",
    "batch_parse",
    "TAF",
    "WeatherState",
    "ChangeGroup",
    "Wind",
    "Cloud",
    "weather_code_to_cn",
    "cloud_amount_to_cn",
]
