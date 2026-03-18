"""
数据模型定义
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WindShear(BaseModel):
    """风切变数据"""
    height: int = Field(..., description="风切变高度，单位英尺")
    direction: int = Field(..., description="风向，单位度")
    speed: int = Field(..., description="风速，单位 m/s")
    gust: Optional[int] = Field(None, description="阵风，单位 m/s")


class Wind(BaseModel):
    """风数据"""
    direction: Optional[int] = Field(None, description="风向，单位度")
    speed: Optional[int] = Field(None, description="风速，单位 m/s")
    gust: Optional[int] = Field(None, description="阵风，单位 m/s")
    variable: bool = Field(False, description="是否可变风向")
    wind_shear: Optional[WindShear] = Field(None, description="风切变预报")


class Cloud(BaseModel):
    """云数据"""
    amount: str = Field(..., description="云量：SKC/FEW/SCT/BKN/OVC")
    height: Optional[int] = Field(None, description="云高，单位英尺")
    type: Optional[str] = Field(None, description="云类型：CB/TCU")


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
    type: str = Field(..., description="变化类型：FM/BECMG/TEMPO/PROB")
    probability: Optional[int] = Field(None, description="PROB 的概率百分比")
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    weather: WeatherState
    before_weather: Optional[WeatherState] = Field(None, description="BECMG 变化前的天气状态（用于取较差值）")


class TEMPODetail(BaseModel):
    """TEMPO 明细项"""
    time_range: str = Field(..., description="时段")
    visibility: Optional[int] = Field(None, description="能见度（米）")
    weather: List[str] = Field(default_factory=list, description="天气现象")
    wind_direction: Optional[int] = Field(None, description="风向（度）")
    wind_speed: Optional[int] = Field(None, description="风速（m/s）")
    wind_gust: Optional[int] = Field(None, description="阵风（m/s）")
    wind_shear: Optional[dict] = Field(None, description="风切变预报")
    clouds: List[dict] = Field(default_factory=list, description="云况列表")


class TAF(BaseModel):
    """TAF 完整数据"""
    raw: str = Field(..., description="原始 TAF 文本")
    icao: str = Field(..., description="机场 ICAO 代码")
    issue_time: datetime = Field(..., description="发布时间")
    valid_from: datetime = Field(..., description="有效开始时间")
    valid_to: datetime = Field(..., description="有效结束时间")
    initial: WeatherState = Field(..., description="初始天气状态")
    changes: List[ChangeGroup] = Field(default_factory=list, description="变化组")
    max_temp: Optional[int] = Field(None, description="最高温度")
    min_temp: Optional[int] = Field(None, description="最低温度")


class TAFDisplay(BaseModel):
    """TAF 显示数据 - 主体和 TEMPO 分开"""
    main: WeatherState = Field(..., description="主体天气状态")
    tempo: Optional[WeatherState] = Field(None, description="TEMPO 最坏情况汇总")
    tempo_details: List[TEMPODetail] = Field(default_factory=list, description="TEMPO 明细列表")
    tempo_groups: List[ChangeGroup] = Field(default_factory=list, description="所有生效的 TEMPO 组（原始数据）")
