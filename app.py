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

from parser import parse_taf, get_weather_at_time, get_weather_display_at_time, TAFParseError
from utils import weather_code_to_cn, cloud_amount_to_cn
from models import WeatherState, TAFDisplay, ChangeGroup


def get_becmg_status(changes: list, query_time: datetime) -> str:
    """
    获取 BECMG 状态

    - 起始时间点显示"变化中"
    - 结束时间点显示"完成"
    - 中间时间点显示"变化中"
    - 如果与 FM/TL/AT 组合，也仅显示"变化"
    """
    for change in changes:
        # 检查 BECMG 类型（包括 BECMG、BECMG FM 等组合）
        if change.type.startswith('BECMG'):
            if not change.from_time or not change.to_time:
                continue

            # 检查是否在 BECMG 时间段内
            if change.from_time <= query_time <= change.to_time:
                # 检查是否同时有 FM/TL/AT 组合
                has_fm_tl_at = ('FM' in change.type or 'TL' in change.type or 'AT' in change.type)

                if query_time == change.from_time:
                    return "变化" if has_fm_tl_at else "变化中"
                elif query_time == change.to_time:
                    return "完成"
                else:
                    return "变化中" if not has_fm_tl_at else "变化"

    return "-"


def get_fm_status(changes: list, query_time: datetime) -> str:
    """
    获取 FM 状态

    - FM、TL、AT 所在的时间点显示"变化"
    - 与 BECMG 组合时不显示（因为已在 BECMG 列显示"变化"）
    """
    for change in changes:
        change_type = change.type

        # 跳过与 BECMG 组合的情况（在 BECMG 列已处理）
        if change_type.startswith('BECMG') and ('FM' in change_type or 'TL' in change_type or 'AT' in change_type):
            continue

        # 检查 FM 变化组（单独的 FM，不与 BECMG 组合）
        if change_type == 'FM' or (change_type.startswith('FM') and not change_type.startswith('BECMG')):
            if change.from_time and query_time == change.from_time:
                return "变化"

        # 检查 TL (TILL) 和 AT (AT TIME) 标记
        if change_type in ('TL', 'AT'):
            if change.from_time and query_time == change.from_time:
                return "变化"

    return "-"


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

    st.header("🌍 时区设置")
    st.info("TAF 报文使用协调世界时 (UTC)")
    timezone_choice = st.selectbox(
        "时间显示",
        ["仅 UTC", "UTC + 北京时间 (UTC+8)", "仅北京时间"],
        index=0,
    )


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
            st.subheader("📈 每小时天气趋势")

            # CSS 样式 - 统一表格字体大小，避免多行文本导致字体渲染过大
            st.markdown("""
                <style>
                div[data-testid="stDataFrame"] table {
                    font-size: 14px !important;
                }
                div[data-testid="stTable"] table {
                    font-size: 14px !important;
                }
                div[data-testid="stDataFrame"] td, div[data-testid="stTable"] td {
                    font-size: 14px !important;
                    line-height: 1.2 !important;
                }
                </style>
            """, unsafe_allow_html=True)

            # 创建每小时时间线数据
            timeline_data = []
            current_time = taf.valid_from
            while current_time <= taf.valid_to:
                weather_display = get_weather_display_at_time(taf, current_time)
                weather = weather_display.main

                # 状态图标和文字描述
                status_icon = "☀️" if weather.cavok else "🌤️"
                status_text = "CAVOK" if weather.cavok else "一般"
                # 根据 TEMPO 天气更新状态
                if weather_display.tempo:
                    if "TS" in str(weather_display.tempo.weather):
                        status_icon = "⛈️"
                        status_text = "雷暴"
                    elif "RA" in str(weather_display.tempo.weather):
                        status_icon = "🌧️"
                        status_text = "降雨"
                elif weather.weather:
                    if "TS" in str(weather.weather):
                        status_icon = "⛈️"
                        status_text = "雷暴"
                    elif "RA" in str(weather.weather):
                        status_icon = "🌧️"
                        status_text = "降雨"
                    elif "SN" in str(weather.weather):
                        status_icon = "🌨️"
                        status_text = "降雪"
                    elif "BR" in str(weather.weather) or "FG" in str(weather.weather):
                        status_icon = "🌫️"
                        status_text = "雾/轻雾"
                    elif "SA" in str(weather.weather) or "SS" in str(weather.weather) or "DS" in str(weather.weather):
                        status_icon = "🌪️"
                        status_text = "沙尘"
                    elif "HZ" in str(weather.weather):
                        status_icon = "🌫️"
                        status_text = "霾"

                vis_text = "CAVOK" if weather.cavok else f"{weather.visibility}m"
                weather_cn = [weather_code_to_cn(w) for w in weather.weather]

                # 处理时区显示
                utc_str = current_time.strftime("%H:%M")
                local_str = (current_time + timedelta(hours=8)).strftime("%m-%d %H:%M")

                if timezone_choice == "仅 UTC":
                    time_display = f"{current_time.strftime('%m-%d %H:%M')} UTC"
                elif timezone_choice == "仅北京时间":
                    time_display = f"{local_str} 北京"
                else:  # UTC + 北京时间
                    time_display = f"{utc_str} UTC / {local_str} 北京"

                # 显示风力信息
                wind_info = "-"
                if weather.wind:
                    if weather.wind.variable:
                        wind_info = "VRB"
                    else:
                        wind_info = f"{weather.wind.direction}°/{weather.wind.speed}m/s"
                    if weather.wind.gust:
                        wind_info += f"(G{weather.wind.gust})"

                # 显示云层信息
                cloud_info = "-"
                if weather.clouds:
                    cloud_info = " | ".join([
                        f"{cloud_amount_to_cn(c.amount)} {c.height}ft"
                        for c in weather.clouds
                    ])

                # TEMPO 明细显示 - 拆分为独立列
                tempo_rows = []
                if weather_display.tempo_details:
                    for detail in weather_display.tempo_details:
                        # 能见度
                        vis_str = f"{detail.visibility}m" if detail.visibility else "-"
                        # 风
                        if detail.wind_speed:
                            if detail.wind_direction:
                                wind_str = f"{detail.wind_direction}°/{detail.wind_speed}m/s"
                            else:
                                wind_str = f"{detail.wind_speed}m/s"
                            if detail.wind_gust:
                                wind_str += f"(G{detail.wind_gust})"
                        else:
                            wind_str = "-"
                        # 云
                        if detail.clouds:
                            cloud_strs = []
                            for c in detail.clouds:
                                s = cloud_amount_to_cn(c['amount'])
                                if c.get('height'):
                                    s += f"({c['height']}ft)"
                                if c.get('type'):
                                    s += c['type']
                                cloud_strs.append(s)
                            cloud_str = " | ".join(cloud_strs)
                        else:
                            cloud_str = "-"
                        # 天气现象
                        wx_str = " | ".join([weather_code_to_cn(w) for w in detail.weather]) if detail.weather else "-"

                        tempo_rows.append({
                            "time_range": detail.time_range,
                            "visibility": vis_str,
                            "wind": wind_str,
                            "cloud": cloud_str,
                            "weather": wx_str,
                        })

                # 主行数据 - 主体天气（不包含 TEMPO 数据）
                main_row = {
                    "时间": time_display,
                    "状态": f"{status_icon} {status_text}",
                    "主体 - 风": wind_info,
                    "主体 - 能见度": vis_text,
                    "主体 - 天气": " | ".join(weather_cn) if weather_cn else "-",
                    "主体 - 云": cloud_info,
                }

                # TEMPO 列 - 只放 TEMPO 相关数据，多个 TEMPO 用换行分隔
                if not tempo_rows:
                    main_row["TEMPO 时段"] = "-"
                    main_row["TEMPO 能见度"] = "-"
                    main_row["TEMPO 风"] = "-"
                    main_row["TEMPO 云"] = "-"
                    main_row["TEMPO 天气"] = "-"
                    main_row["TEMPO 最坏情况"] = "-"
                else:
                    # 收集所有 TEMPO 的值
                    tempo_times = [row["time_range"] for row in tempo_rows]
                    tempo_vis = [row["visibility"] for row in tempo_rows]
                    tempo_wind = [row["wind"] for row in tempo_rows]
                    tempo_cloud = [row["cloud"] for row in tempo_rows]
                    tempo_weather_list = [row["weather"] for row in tempo_rows]

                    # 多个 TEMPO 用换行分隔显示（使用纯文本换行，避免 markdown 渲染导致字体变大）
                    main_row["TEMPO 时段"] = "\n".join(tempo_times)
                    main_row["TEMPO 能见度"] = "\n".join(tempo_vis)
                    main_row["TEMPO 风"] = "\n".join(tempo_wind)
                    main_row["TEMPO 云"] = "\n".join(tempo_cloud)
                    main_row["TEMPO 天气"] = "\n".join(tempo_weather_list)

                    # TEMPO 最坏情况（多个 TEMPO 时）
                    if weather_display.tempo and len(tempo_rows) > 1:
                        worst_vis = f"{weather_display.tempo.visibility}m" if weather_display.tempo.visibility else "-"
                        worst_wx = " | ".join([weather_code_to_cn(w) for w in weather_display.tempo.weather]) if weather_display.tempo.weather else "-"
                        main_row["TEMPO 最坏情况"] = f"{worst_vis} {worst_wx}"
                    else:
                        main_row["TEMPO 最坏情况"] = "-"

                # BECMG 列 - 检查是否有 BECMG 变化组
                becmg_status = get_becmg_status(taf.changes, current_time)
                main_row["BECMG"] = becmg_status

                # FM 列 - 检查是否有 FM 变化组
                fm_status = get_fm_status(taf.changes, current_time)
                main_row["FM"] = fm_status

                timeline_data.append(main_row)

                current_time += timedelta(hours=1)

            # 使用 dataframe 替代 table，并通过 CSS 统一字体大小
            st.dataframe(
                timeline_data,
                use_container_width=True,
                hide_index=True,
            )

        # 显示查询时间的天气
        st.divider()
        # 查询时间显示（带时区）
        if timezone_choice == "仅 UTC":
            query_time_str = f"{query_time.strftime('%Y-%m-%d %H:%M')} UTC"
        elif timezone_choice == "仅北京时间":
            query_time_str = f"{(query_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')} 北京"
        else:  # UTC + 北京时间
            query_time_str = f"{query_time.strftime('%H:%M')} UTC / {(query_time + timedelta(hours=8)).strftime('%m-%d %H:%M')} 北京"

        st.subheader(f"🌍 {query_time_str} 的天气")

        # 获取分开的主体和 TEMPO 数据
        weather_display = get_weather_display_at_time(taf, query_time)

        # 显示主体天气
        st.markdown("### 主体天气")
        display_weather(weather_display.main)

        # 如果有 TEMPO，分开显示
        if weather_display.tempo_details:
            st.divider()
            st.markdown("### ⚠️ TEMPO 明细")

            # 显示 TEMPO 明细表
            tempo_header = ["时段", "能见度", "风", "云", "天气现象"]
            tempo_rows = []
            for detail in weather_display.tempo_details:
                # 能见度
                vis_str = f"{detail.visibility}m" if detail.visibility else "-"
                # 风
                if detail.wind_speed:
                    if detail.wind_direction:
                        wind_str = f"{detail.wind_direction}°/{detail.wind_speed}m/s"
                    else:
                        wind_str = f"{detail.wind_speed}m/s"
                    if detail.wind_gust:
                        wind_str += f"(G{detail.wind_gust})"
                else:
                    wind_str = "-"
                # 云
                if detail.clouds:
                    cloud_strs = []
                    for c in detail.clouds:
                        s = cloud_amount_to_cn(c['amount'])
                        if c.get('height'):
                            s += f"({c['height']}ft)"
                        if c.get('type'):
                            s += c['type']
                        cloud_strs.append(s)
                    cloud_str = " | ".join(cloud_strs)
                else:
                    cloud_str = "-"
                # 天气现象
                wx_str = " | ".join([weather_code_to_cn(w) for w in detail.weather]) if detail.weather else "-"

                tempo_rows.append([detail.time_range, vis_str, wind_str, cloud_str, wx_str])

            st.table(dict(zip(tempo_header, zip(*tempo_rows))) if tempo_rows else {})

            # 显示最坏情况
            if weather_display.tempo:
                st.markdown("#### 📉 TEMPO 最坏情况（汇总）")
                st.info("以下显示多个 TEMPO 叠加后的最坏情况（能见度/云底高取最小，风取最大，天气取并集）")
                display_weather(weather_display.tempo)


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
