#!/usr/bin/env python3
"""
TAF Parse 使用示例

输入：机场TAF报文、时间
输出：基于输入时间的机场天气
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加 src 到路径
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from parser import parse_taf, get_weather_at_time
from utils import weather_code_to_cn, cloud_amount_to_cn


def main():
    print("="*70)
    print("TAF 解析器 - 使用示例")
    print("="*70)

    # 示例 TAF 报文
    taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040"""

    print("\n输入 TAF 报文:")
    print("-"*70)
    print(taf_text)
    print("-"*70)

    # 解析 TAF
    print("\n正在解析...")
    taf = parse_taf(taf_text)

    print(f"\n解析结果:")
    print(f"  机场: {taf.icao}")
    print(f"  发布时间: {taf.issue_time}")
    print(f"  有效期: {taf.valid_from} 至 {taf.valid_to}")
    print(f"  变化组: {len(taf.changes)} 个")

    # 设置基准日期
    base_date = taf.issue_time.replace(hour=0, minute=0, second=0, microsecond=0)

    # 测试不同时间
    test_queries = [
        ("12:00", base_date.replace(hour=12)),
        ("14:30", base_date.replace(hour=14, minute=30)),
        ("15:00", base_date.replace(hour=15)),
        ("17:30", base_date.replace(hour=17, minute=30)),
        ("20:00", base_date.replace(hour=20)),
        ("次日 02:00", base_date.replace(hour=2) + timedelta(days=1)),
    ]

    for time_label, query_time in test_queries:
        print(f"\n{'─'*50}")
        print(f"查询时间: {time_label} ({query_time})")
        print(f"{'─'*50}")

        try:
            weather = get_weather_at_time(taf, query_time)

            if weather.cavok:
                print("  ☀️ CAVOK - 天气良好")
            else:
                if weather.wind:
                    wind_str = []
                    if weather.wind.variable:
                        wind_str.append("风向: 可变")
                    else:
                        wind_str.append(f"风向: {weather.wind.direction}°")
                    wind_str.append(f"风速: {weather.wind.speed} m/s")
                    if weather.wind.gust:
                        wind_str.append(f"阵风: {weather.wind.gust} m/s")
                    print(f"  💨 {' | '.join(wind_str)}")

                if weather.visibility:
                    print(f"  👁️ 能见度: {weather.visibility} 米")

                if weather.weather:
                    weather_cn = [weather_code_to_cn(w) for w in weather.weather]
                    print(f"  🌤️ 天气: {' | '.join(weather_cn)}")

                if weather.clouds:
                    cloud_str = []
                    for cloud in weather.clouds:
                        s = cloud_amount_to_cn(cloud.amount)
                        if cloud.height:
                            s += f" ({cloud.height}英尺)"
                        if cloud.type:
                            s += f" {cloud.type}"
                        cloud_str.append(s)
                    print(f"  ☁️ 云况: {' | '.join(cloud_str)}")

        except ValueError as e:
            print(f"  ❌ {e}")

    print("\n" + "="*70)
    print("完成!")
    print("="*70)


if __name__ == "__main__":
    main()
