# TAF Parse - 机场天气预报解析器

## 项目概述

TAF (Terminal Aerodrome Forecast) 是航空业使用的标准机场天气预报格式。本项目用于解析和处理 TAF 气象数据，将其转换为结构化数据供航空业务使用。

**核心功能：**
- ✅ 输入：机场TAF报文、时间
- ✅ 输出：基于输入时间的机场天气

## 背景与目标

### 什么是 TAF？
TAF 是由世界气象组织 (WMO) 定义的机场天气预报格式，通常包含：
- 机场 ICAO 代码
- 预报有效时间
- 风向风速
- 能见度
- 天气现象
- 云况
- 温度预报（可选）
- 变化组（FM、BECMG、TEMPO、PROB）

### 项目目标
- ✅ 解析原始 TAF 文本为结构化数据
- ✅ 根据指定时间获取对应天气状态
- ✅ 支持中文气象术语映射
- 支持多种 TAF 格式变体
- 提供验证和纠错功能
- 输出 JSON/CSV 等格式

## 目录结构

```
taf_parse/
├── README.md              # 本文件
├── app.py                 # Streamlit Web 应用
├── run_app.sh             # Web 应用启动脚本
├── example.py             # 命令行示例
├── requirements.txt       # Python依赖
├── .gitignore
├── src/                   # 源代码
│   ├── __init__.py
│   ├── parser.py          # TAF 解析核心逻辑
│   ├── validator.py       # 数据验证
│   ├── models.py          # 数据模型定义
│   └── utils.py           # 工具函数（含中文映射）
├── data/                  # 数据目录
│   ├── raw/               # 原始 TAF 数据
│   └── processed/         # 处理后的数据
├── tests/                 # 测试
│   ├── test_parser.py     # 单元测试
│   ├── test_integration.py # 集成测试
│   └── test_examples/     # 测试用例 TAF 样本
├── notebooks/             # Jupyter notebooks
│   └── exploration.ipynb
└── docs/                  # 文档
    ├── TAF_format.md      # TAF 格式详细说明
    └── 使用示例.md        # 使用示例和代码
```

## Web 界面功能

Streamlit Web 应用提供：

- 📋 **预设示例**：北京首都、上海浦东、广州白云机场的 TAF 示例
- 🕐 **时间选择器**：可选择预报有效期内的任意时间
- 📊 **可视化展示**：风、能见度、天气现象、云况的直观展示
- 📈 **天气时间线**：以表格形式展示整个预报期的天气变化
- 🌍 **中文显示**：天气现象和云量的中文翻译
- 🔧 **原始数据**：可查看解析后的 JSON 原始数据

## 快速开始

### 方式1：运行 Web 测试界面（推荐）

```bash
cd aviation/projects/taf_parse
./run_app.sh

# 或者直接运行
streamlit run app.py
```

然后在浏览器中访问显示的 URL（通常是 http://localhost:8501）

### 方式2：运行命令行示例

```bash
cd aviation/projects/taf_parse
python example.py
```

### TAF 格式示例

典型 TAF 报文：
```
TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040
```

## 使用方法

### 1. 解析 TAF 并获取指定时间的天气

```python
from src.parser import parse_taf, get_weather_at_time
from src.utils import weather_code_to_cn, cloud_amount_to_cn
from datetime import datetime

# 输入 TAF 报文
taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010"""

# 解析 TAF
taf = parse_taf(taf_text)

# 设置查询时间
base_date = taf.issue_time.replace(hour=0, minute=0, second=0, microsecond=0)
query_time = base_date.replace(hour=15)  # 15:00

# 获取该时间的天气
weather = get_weather_at_time(taf, query_time)

# 输出结果
print(f"能见度: {weather.visibility} 米")
if weather.wind:
    print(f"风向: {weather.wind.direction}°, 风速: {weather.wind.speed} m/s")
for w in weather.weather:
    print(f"天气: {weather_code_to_cn(w)}")
for c in weather.clouds:
    print(f"云况: {cloud_amount_to_cn(c.amount)}")
```

### 2. 批量处理

```python
from src.parser import batch_parse

batch_parse("data/raw/", "data/processed/")
```

## 数据模型

### TAF - 完整预报
```python
class TAF:
    icao: str                    # 机场代码
    issue_time: datetime         # 发布时间
    valid_from: datetime         # 有效开始时间
    valid_to: datetime           # 有效结束时间
    initial: WeatherState        # 初始天气状态
    changes: List[ChangeGroup]   # 变化组
```

### WeatherState - 天气状态
```python
class WeatherState:
    wind: Optional[Wind]         # 风
    visibility: Optional[int]     # 能见度（米）
    cavok: bool                   # CAVOK - 天气良好
    weather: List[str]            # 天气现象
    clouds: List[Cloud]           # 云况
```

### Wind - 风数据
```python
class Wind:
    direction: Optional[int]      # 风向（度）
    speed: Optional[int]          # 风速（m/s）
    gust: Optional[int]           # 阵风（m/s）
    variable: bool                # 是否可变风向
```

## 环境设置

### Python 环境
```bash
# 创建虚拟环境
conda create -n taf_parse python=3.10
conda activate taf_parse

# 安装依赖
pip install -r requirements.txt
```

### 依赖项
- Python 3.10+
- pydantic - 数据验证

## 开发进度

- [x] 项目结构搭建
- [x] TAF 格式文档整理
- [x] 基础解析器实现
- [x] 根据时间获取天气功能
- [x] 中文术语映射
- [x] 测试用例
- [ ] 完整验证逻辑
- [ ] 更多 TAF 变体支持

## 参考文献

- ICAO Annex 3 - Meteorological Service for International Air Navigation
- WMO No. 306 - Manual on Codes
- FAA TAF 用户指南
