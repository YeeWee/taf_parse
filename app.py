#!/usr/bin/env python3
"""
TAF Parse - Web 测试页面

使用 Streamlit 构建的 TAF 解析器测试界面
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st

# 添加 src 到路径
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from parser import parse_taf, get_weather_at_time, TAFParseError
from utils import weather_code_to_cn, cloud_amount_to_cn
from models import WeatherState


# 页面配置
st.set_page_config(
    page_title="TAF 解析器",
    page_icon="✈️",
    layout="wide",
)

# 标题
st.title("✈️ TAF 机场天气预报解析器")
st.markdown("输入 TAF 报文和查询时间，获取对应的天气状况")


# 示例 TAF
SAMPLE_TAFS = {
    "北京首都 (ZBAA)": """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040""",

    "上海浦东 (ZSPD)": """TAF ZSPD 050600Z 0509/0615 09003MPS CAVOK
BECMG 0512/0514 15006MPS
TEMPO 0515/0519 3000 BR
BECMG 0521/0523 08002MPS""",

    "广州白云 (ZGGG)": """TAF ZGGG 050400Z 0506/0612 15003MPS 8000 FEW020 SCT040
BECMG 0508/0510 02008G15MPS 6000 -SHRA SCT020 BKN040
TEMPO 0512/0518 3000 TSRA BKN015CB
BECMG 0520/0522 13004MPS 9999 NSW SCT030""",
}


def display_weather(weather: WeatherState):
    """显示天气状态"""
    if weather.cavok:
        st.success("☀️ **CAVOK - 天气良好**")
        st.info("能见度 ≥ 10km，无重要天气，云高 ≥ 1500英尺")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("💨 风")
        if weather.wind:
            if weather.wind.variable:
                st.write("风向：**可变**")
            else:
                st.write(f"风向：**{weather.wind.direction}°**")
            st.write(f"风速：**{weather.wind.speed} m/s**")
            if weather.wind.gust:
                st.write(f"阵风：**{weather.wind.gust} m/s**")
        else:
            st.write("无数据")

    with col2:
        st.subheader("👁️ 能见度")
        if weather.visibility:
            if weather.visibility >= 10000:
                st.write(f"**≥ 10 km**")
            else:
                st.write(f"**{weather.visibility} 米**")
        else:
            st.write("无数据")

    with col3:
        st.subheader("🌤️ 天气现象")
        if weather.weather:
            for w in weather.weather:
                cn = weather_code_to_cn(w)
                st.write(f"- **{w}** ({cn})")
        else:
            st.write("无重要天气")

    st.subheader("☁️ 云况")
    if weather.clouds:
        cloud_cols = st.columns(len(weather.clouds))
        for i, cloud in enumerate(weather.clouds):
            with cloud_cols[i]:
                cn_amount = cloud_amount_to_cn(cloud.amount)
                st.metric(
                    label=cn_amount,
                    value=f"{cloud.height} ft" if cloud.height else "-",
                    delta=cloud.type if cloud.type else None,
                )
    else:
        st.write("无云数据")


# 侧边栏
with st.sidebar:
    st.header("📋 示例 TAF")
    sample_choice = st.selectbox(
        "选择示例",
        ["自定义"] + list(SAMPLE_TAFS.keys()),
        index=0,
    )

    st.header("⚙️ 显示选项")
    show_raw = st.checkbox("显示原始解析数据", value=False)
    show_timeline = st.checkbox("显示时间线", value=True)


# 主界面
# 先显示 TAF 输入区域
st.subheader("📝 TAF 报文")

if sample_choice != "自定义":
    taf_text = st.text_area(
        "TAF 报文",
        value=SAMPLE_TAFS[sample_choice],
        height=180,
    )
else:
    taf_text = st.text_area(
        "TAF 报文",
        placeholder="请输入 TAF 报文...",
        height=180,
    )

# 解析 TAF
taf = None
if taf_text.strip():
    try:
        taf = parse_taf(taf_text)

        # 计算有效期内的小时
        hours = []
        current = taf.valid_from
        while current <= taf.valid_to:
            hours.append(current)
            current += timedelta(hours=1)

        time_labels = [h.strftime("%m-%d %H:00") for h in hours]

        # 显示查询时间选择器
        st.subheader("🕐 查询时间")
        selected_time_label = st.selectbox(
            "选择时间",
            time_labels,
            index=0,
        )
        # 根据选中的标签找到对应的时间
        query_time = hours[time_labels.index(selected_time_label)]

        # 显示解析的基本信息
        st.divider()
        st.subheader("📊 解析结果")

        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        info_col1.metric("机场", taf.icao)
        info_col2.metric("发布时间", taf.issue_time.strftime("%m-%d %H:%M"))
        info_col3.metric("有效期开始", taf.valid_from.strftime("%m-%d %H:%M"))
        info_col4.metric("有效期结束", taf.valid_to.strftime("%m-%d %H:%M"))

        st.write(f"**变化组数量**: {len(taf.changes)}")

        # 显示时间线
        if show_timeline:
            st.divider()
            st.subheader("📈 天气时间线")

            # 创建时间线数据
            timeline_data = []
            current_time = taf.valid_from
            while current_time <= taf.valid_to:
                weather = get_weather_at_time(taf, current_time)
                status = "☀️" if weather.cavok else "🌤️"
                if weather.weather:
                    if "TS" in str(weather.weather):
                        status = "⛈️"
                    elif "RA" in str(weather.weather):
                        status = "🌧️"
                    elif "SN" in str(weather.weather):
                        status = "🌨️"
                    elif "BR" in str(weather.weather) or "FG" in str(weather.weather):
                        status = "🌫️"

                vis_text = "CAVOK" if weather.cavok else f"{weather.visibility}m"
                weather_cn = [weather_code_to_cn(w) for w in weather.weather]

                timeline_data.append({
                    "时间": current_time.strftime("%H:%M"),
                    "状态": status,
                    "能见度": vis_text,
                    "天气": " | ".join(weather_cn) if weather_cn else "-",
                })
                current_time += timedelta(hours=2)

            st.table(timeline_data)

        # 显示查询时间的天气
        st.divider()
        st.subheader(f"🌍 {query_time.strftime('%Y-%m-%d %H:%M')} 的天气")

        weather = get_weather_at_time(taf, query_time)
        display_weather(weather)

        # 显示原始数据
        if show_raw:
            st.divider()
            st.subheader("🔧 原始数据")
            with st.expander("查看完整数据"):
                st.json(weather.model_dump(mode='json'))

    except TAFParseError as e:
        st.error(f"❌ 解析错误: {e}")
    except Exception as e:
        st.error(f"❌ 错误: {e}")
        st.exception(e)

else:
    st.info("👆 请输入或选择一个 TAF 报文")


# 页脚
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <small>TAF Parse v0.2.0 | 基于 ICAO Annex 3 / WMO No. 306 规范</small>
    </div>
    """,
    unsafe_allow_html=True,
)
