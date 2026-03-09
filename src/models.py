"""
数据模型定义
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Wind(BaseModel):
    """风数据"""
    direction: Optional[int] = Field(None, description="风向，单位度")
    speed: Optional[int] = Field(None, description="风速，单位 m/s")
    gust: Optional[int] = Field(None, description="阵风，单位 m/s")
    variable: bool = Field(False, description="是否可变风向")


class Cloud(BaseModel):
    """云数据"""
    amount: str = Field(..., description="云量: SKC/FEW/SCT/BKN/OVC")
    height: Optional[int] = Field(None, description="云高，单位英尺")
    type: Optional[str] = Field(None, description="云类型: CB/TCU")


class WeatherState(BaseModel):
    """天气状态"""
    wind: Optional[Wind] = None
    visibility: Optional[int] = Field(None, description="能见度，单位米")
    cavok: bool = Field(False, description="CAVOK - 天气良好")
    weather: List[str] = Field(default_factory=list, description="天气现象")
    clouds: List[Cloud] = Field(default_factory=list, description="云况")
    temp_min: Optional[int] = Field(None, description="最低温度")
    temp_max: Optional[int] = Field(None, description="最高温度")


class ChangeGroup(BaseModel):
    """变化组"""
    type: str = Field(..., description="变化类型: FM/BECMG/TEMPO/PROB")
    probability: Optional[int] = Field(None, description="PROB的概率百分比")
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    weather: WeatherState


class TAF(BaseModel):
    """TAF 完整数据"""
    raw: str = Field(..., description="原始TAF文本")
    icao: str = Field(..., description="机场ICAO代码")
    issue_time: datetime = Field(..., description="发布时间")
    valid_from: datetime = Field(..., description="有效开始时间")
    valid_to: datetime = Field(..., description="有效结束时间")
    initial: WeatherState = Field(..., description="初始天气状态")
    changes: List[ChangeGroup] = Field(default_factory=list, description="变化组")
    max_temp: Optional[int] = Field(None, description="最高温度")
    min_temp: Optional[int] = Field(None, description="最低温度")
