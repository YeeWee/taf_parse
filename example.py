#!/usr/bin/env python3
"""
TAF Parse 使用示例

输入：机场 TAF 报文、时间
输出：基于输入时间的机场天气

支持的 TAF 格式：
- 标准格式（中国/国际）
- TAF AMD（修订报）、TAF COR（更正报）
- FMDDHHMM 格式（FM 变化组带时间）
- 英制单位（SM 能见度、KT 风速）
- 24 时格式（日界处理）
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加 src 到路径
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from parser import parse_taf, get_weather_at_time, get_weather_display_at_time
from utils import weather_code_to_cn, cloud_amount_to_cn
from models import TEMPODetail


# 示例 TAF 报文
EXAMPLE_TAFS = {
    "中国格式": """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040""",

    "国际格式（英制）": """TAF CYXY 082340Z 0900/0912 28006KT P6SM SCT060 BKN150
TEMPO 0900/0906 5SM -SHSN OVC040
FM090600 33006KT P6SM FEW020 SCT150
RMK NXT FCST BY 090600Z=""",

    "修订报": """TAF AMD ZLDL 040629Z 0406/0415 26019G25MPS 1500 BLSA FEW040 BKN090
TX06/0407Z TNM03/0415Z TEMPO 0408/0409 0700 SS=""",

    "24 时格式": """TAF ZUTF 090304Z 0906/1006 03004MPS 6000 SCT050
TX20/0907Z TN08/0923Z BECMG 0923/0924 2000 BR BECMG 1001/1002 3500=""",

    "多个 TEMPO": """TAF ZSPD 101100Z 1012/1118 36005MPS 9999 FEW040
TEMPO 1014/1018 3000 SHRA BKN020CB
TEMPO 1016/1020 1200 TSRA GR BKN015CB
TEMPO 1020/1024 2000 BR OVC010
BECMG 1100/1102 27008MPS 9999 NSW SCT030""",
}


def display_weather(weather, indent="  ", label=None):
    """显示天气状态"""
    if label:
        print(f"{indent}{label}")

    if weather.cavok:
        print(f"{indent}  ☀️ CAVOK - 天气良好")
        return

    if weather.wind:
        wind_str = []
        if weather.wind.variable:
            wind_str.append("风向：可变")
        else:
            wind_str.append(f"风向：{weather.wind.direction}°")
        wind_str.append(f"风速：{weather.wind.speed} m/s")
        if weather.wind.gust:
            wind_str.append(f"阵风：{weather.wind.gust} m/s")
        print(f"{indent}  💨 {' | '.join(wind_str)}")

    if weather.visibility:
        vis_str = f"{weather.visibility} 米" if weather.visibility < 10000 else "≥ 10 km"
        print(f"{indent}  👁️ 能见度：{vis_str}")

    if weather.weather:
        weather_cn = [weather_code_to_cn(w) for w in weather.weather]
        print(f"{indent}  🌤️ 天气：{' | '.join(weather_cn)}")
    else:
        print(f"{indent}  🌤️ 天气：无重要天气")

    if weather.clouds:
        cloud_str = []
        for cloud in weather.clouds:
            s = cloud_amount_to_cn(cloud.amount)
            if cloud.height:
                s += f" ({cloud.height}英尺)"
            if cloud.type:
                s += f" {cloud.type}"
            cloud_str.append(s)
        print(f"{indent}  ☁️ 云况：{' | '.join(cloud_str)}")
    else:
        print(f"{indent}  ☁️ 云况：无云数据")


def parse_example(taf_name, taf_text):
    """解析并显示示例"""
    print("\n" + "="*70)
    print(f"TAF 示例：{taf_name}")
    print("="*70)

    print("\n原始报文:")
    print("-"*70)
    print(taf_text)
    print("-"*70)

    # 解析 TAF
    print("\n解析结果:")
    taf = parse_taf(taf_text)

    print(f"  机场：{taf.icao}")
    print(f"  发布时间：{taf.issue_time.strftime('%m-%d %H:%M')}")
    print(f"  有效期：{taf.valid_from.strftime('%m-%d %H:%M')} 至 {taf.valid_to.strftime('%m-%d %H:%M')}")
    print(f"  变化组：{len(taf.changes)} 个")

    for i, ch in enumerate(taf.changes):
        ch_type = ch.type
        time_range = ""
        if ch.from_time and ch.to_time:
            time_range = f" ({ch.from_time.strftime('%H:%M')}-{ch.to_time.strftime('%H:%M')})"
        print(f"    [{i+1}] {ch_type}{time_range}")

    # 测试不同时间
    print("\n每小时天气 (部分时段):")
    print("-"*70)

    query_time = taf.valid_from
    count = 0
    while query_time <= taf.valid_to and count < 12:  # 显示前 12 小时
        weather_display = get_weather_display_at_time(taf, query_time)
        time_str = query_time.strftime("%H:%M")
        print(f"\n{time_str}:")

        # 显示主体天气
        display_weather(weather_display.main, indent="    ", label="【主体】")

        # 如果有 TEMPO，显示明细和最坏情况
        if weather_display.tempo_details:
            # 显示 TEMPO 明细表
            print("    【TEMPO 明细】")
            print(f"    {'时段':<12} {'能见度':<10} {'风':<18} {'云':<20} {'天气现象'}")
            print("    " + "-"*80)
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

                print(f"    {detail.time_range:<12} {vis_str:<10} {wind_str:<18} {cloud_str:<20} {wx_str}")

            # 显示最坏情况
            if weather_display.tempo:
                print()
                display_weather(weather_display.tempo, indent="    ", label="【TEMPO 最坏情况】")

        query_time += timedelta(hours=1)
        count += 1

    return taf


def main():
    print("="*70)
    print("TAF 解析器 - 使用示例")
    print("="*70)

    # 解析所有示例
    for name, taf_text in EXAMPLE_TAFS.items():
        parse_example(name, taf_text)
        print()

    print("="*70)
    print("完成! 访问 Web 界面查看更多示例:")
    print("  streamlit run app.py")
    print("="*70)


if __name__ == "__main__":
    main()
