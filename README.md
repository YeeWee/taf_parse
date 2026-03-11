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
- ✅ 支持多种 TAF 格式变体（TAF AMD、TAF COR、FMDDHHMM 等）
- ✅ 支持英制单位（能见度 SM、风速 KT）
- ✅ 输出 JSON/CSV 等格式

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
- 📈 **天气时间线**：以表格形式展示整个预报期的天气变化（每小时数据）
- 🌍 **中文显示**：天气现象和云量的中文翻译
- 🌐 **时区显示**：支持 UTC、北京时间 (UTC+8) 或同时显示
- 🔧 **原始数据**：可查看解析后的 JSON 原始数据
- 📝 **变化组展示**：TEMPO、BECMG、FM 变化组的详细显示
- 📊 **每小时天气趋势表格**：主体天气与 TEMPO 分开显示，新增 BECMG、FM 状态列

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

典型 TAF 报文（中国格式）：
```
TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040
```

国际格式（英制单位）：
```
TAF CYXY 082340Z 0900/0912 28006KT P6SM SCT060 BKN150
TEMPO 0900/0906 5SM -SHSN OVC040
FM090600 33006KT P6SM FEW020 SCT150
```

修订报和更正报：
```
TAF AMD ZLDL 040629Z 0406/0415 26019G25MPS 1500 BLSA FEW040
TAF COR ZSPD 050600Z 0509/0615 09003MPS CAVOK
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

## TEMPO 处理逻辑

当同一时段有多个 TEMPO 组生效时，系统会自动汇总最坏情况：

| 要素 | 逻辑 | 示例 |
|------|------|------|
| **能见度** | 取最小值 | 3000m + 1200m → **1200m** |
| **云底高** | 取最低值（不分云量） | BKN020 + OVC015 → **OVC015** |
| **风速** | 取最大值 | 10m/s + 15m/s → **15m/s** |
| **阵风** | 取最大值 | G20 + G30 → **G30** |
| **风向** | 不同时标记为可变 | 270° + 360° → **VRB** |
| **天气现象** | 按严重程度排序，去重 | SHRA + TSRA → **TSRA** |

### 每小时天气趋势表格

表格列说明：

| 列 | 说明 |
|----|------|
| **时间** | 显示 UTC 时间、北京时间或同时显示（可配置） |
| **状态** | 天气状态图标和描述（一般/雷暴/降雨等） |
| **主体 - 风/能见度/天气/云** | 主体天气预报数据 |
| **TEMPO 时段/能见度/风/云/天气** | TEMPO 变化组数据（多个 TEMPO 时分行显示） |
| **TEMPO 最坏情况** | 多个 TEMPO 叠加后的最坏情况汇总 |
| **BECMG** | 渐变变化组状态（变化中/完成/-） |
| **FM** | 固定时刻变化组状态（变化/-） |

### BECMG 列显示规则

| 时间点 | 显示 |
|--------|------|
| BECMG 起始时间 | `变化中` |
| BECMG 中间时间 | `变化中` |
| BECMG 结束时间 | `完成` |
| BECMG 与 FM/TL/AT 组合 | 起始时间显示 `变化` |
| 无 BECMG | `-` |

### FM 列显示规则

| 时间点 | 显示 |
|--------|------|
| FM 生效时间 | `变化` |
| TL（Till）时间 | `变化` |
| AT（At）时间 | `变化` |
| 与 BECMG 组合时 | 在 BECMG 列显示，FM 列为 `-` |

### 多 TEMPO 同时显示

同一时间有多个 TEMPO 生效时，TEMPO 相关列会分行显示每个 TEMPO 的状态：

```
TEMPO 时段       TEMPO 能见度    TEMPO 风        TEMPO 天气
16:00-18:00      1500m         320°/10m/s     雷暴
18:00-20:00      3000m         VRB/5m/s       小雨
```

### 天气现象严重程度（从高到低）

1. **雷暴 + 降水/冰雹** (TSGR、TSGS、TSRA、TSPL、TSSN、TS) - 最严重
2. **沙暴/尘暴** (SS、DS) - 非常严重
3. **冻雨** (FZRA、FZDZ) - 严重（航空器结冰危险）
4. **冰雹** (GR、GS)
5. **普通降水** (RA、SN、PE、DZ、SG) - 中等
6. **阵性降水** (SHRA、SHSN、SHGR 等)
7. **雾** (FG) - 严重影响能见度
8. **轻雾/霾** (BR、HZ) - 较轻

### 天气现象包含关系去重

- `TSRA` 包含 `RA`、`SHRA`（雷暴阵雨包含普通降雨和阵雨）
- `TSSN` 包含 `SN`、`SHSN`（雷暴阵雪包含普通降雪和阵雪）
- `TSGR` 包含 `GR`（雷暴伴冰雹包含冰雹）
- `FZRA` 包含 `RA`（冻雨包含普通降雨）
- `FZDZ` 包含 `DZ`（冻毛毛雨包含普通毛毛雨）
- `SHRA` 包含 `RA`（阵雨包含普通降雨）
- `+RA` 比 `RA` 严重（强度前缀）
- `FG` 包含 `MIFG`、`BCFG` 等（雾包含浅雾、碎雾等）

### 示例

```
TEMPO 14:00-18:00  3000m  SHRA  BKN020CB
TEMPO 16:00-20:00  1200m  TSRA GR  BKN015CB

最坏情况汇总:
- 能见度：1200m (取最小)
- 天气：TSRA | GR (TSRA 包含 SHRA，GR 独立保留)
- 云：BKN015CB (取最低云底高)
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
- [x] 支持 TAF AMD/COR 修订报/更正报
- [x] 支持 24 时格式（日界处理，如 0924 表示 10 日 00:00）
- [x] 支持英制单位（SM 能见度、KT 风速）
- [x] 支持 FMDDHHMM 格式（FM 变化组带时间）
- [x] 支持天气现象完整解析（强度、特征、类型）
- [x] 支持 WMO 报头格式（如 FTUS31 KWBC 071740）
- [x] 每小时天气时间线展示
- [x] TEMPO/BECMG/FM 变化组详细展示
- [x] 时区显示选项（UTC、北京时间）
- [ ] 完整验证逻辑
- [x] 更多 TAF 变体支持（PROB、INTER 等）

## 参考文献

- ICAO Annex 3 - Meteorological Service for International Air Navigation
- WMO No. 306 - Manual on Codes
- 中国民用航空气象报文规范
- FAA TAF 用户指南

## 版本历史

- v0.6.0 (2026-03) - 支持 WMO 报头格式（如 FTUS31 KWBC 071740）
- v0.5.0 (2026-03) - 每小时趋势表格：主体与 TEMPO 分开、新增 BECMG/FM 列、多 TEMPO 分行显示
- v0.4.0 (2026-03) - TEMPO 主体分开显示、TEMPO 明细表、最坏情况汇总逻辑
- v0.3.0 (2026-03) - 完整支持 FM 变化组、英制单位、时区显示
- v0.2.0 - 支持 TEMPO 可视化、每小时时间线
- v0.1.0 - 基础解析功能
