"""
TAF 解析器集成测试
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加 src 到路径
src_path = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, src_path)

from parser import parse_taf, get_weather_at_time
from utils import weather_code_to_cn, cloud_amount_to_cn


def print_weather(weather, title="天气状态"):
    """打印天气状态"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

    if weather.cavok:
        print("✓ CAVOK - 天气良好")
    else:
        if weather.wind:
            wind_info = []
            if weather.wind.variable:
                wind_info.append("风向: 可变")
            else:
                wind_info.append(f"风向: {weather.wind.direction}°")
            wind_info.append(f"风速: {weather.wind.speed} m/s")
            if weather.wind.gust:
                wind_info.append(f"阵风: {weather.wind.gust} m/s")
            print(f"风: {', '.join(wind_info)}")

        if weather.visibility:
            print(f"能见度: {weather.visibility} 米")

        if weather.weather:
            weather_cn = [weather_code_to_cn(w) for w in weather.weather]
            print(f"天气现象: {', '.join(weather.weather)} ({', '.join(weather_cn)})")

        if weather.clouds:
            cloud_info = []
            for cloud in weather.clouds:
                info = cloud_amount_to_cn(cloud.amount)
                if cloud.height:
                    info += f" {cloud.height}英尺"
                if cloud.type:
                    info += f" {cloud.type}"
                cloud_info.append(info)
            print(f"云况: {', '.join(cloud_info)}")


def test_sample1():
    """测试样本1 - 北京首都机场"""
    print("\n" + "="*80)
    print("测试1: 北京首都机场 TAF")
    print("="*80)

    taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010
TEMPO 0516/0520 1500 TSRA
BECMG 0522/0600 20005MPS 9999 NSW SCT040"""

    # 解析 TAF
    taf = parse_taf(taf_text)
    print(f"\n机场: {taf.icao}")
    print(f"发布时间: {taf.issue_time}")
    print(f"有效期: {taf.valid_from} 至 {taf.valid_to}")
    print(f"变化组数量: {len(taf.changes)}")

    # 打印初始天气
    print_weather(taf.initial, "初始天气 (12:00-14:00)")

    # 测试不同时间点的天气
    # 使用发布时间的日期作为基准
    base_date = taf.issue_time.replace(hour=0, minute=0, second=0, microsecond=0)

    test_times = [
        ("12:00 (初始)", base_date.replace(hour=12)),
        ("15:00 (BECMG后)", base_date.replace(hour=15)),
        ("17:00 (TEMPO中)", base_date.replace(hour=17)),
        ("21:00 (TEMPO后)", base_date.replace(hour=21)),
        ("次日 06:00", base_date.replace(hour=6) + timedelta(days=1)),
    ]

    for time_label, query_time in test_times:
        try:
            weather = get_weather_at_time(taf, query_time)
            print_weather(weather, f"{time_label} 的天气")
        except ValueError as e:
            print(f"\n{time_label}: {e}")


def test_sample2():
    """测试样本2 - 上海浦东机场"""
    print("\n" + "="*80)
    print("测试2: 上海浦东机场 TAF")
    print("="*80)

    taf_text = """TAF ZSPD 050600Z 0509/0615 09003MPS CAVOK
BECMG 0512/0514 15006MPS
TEMPO 0515/0519 3000 BR
BECMG 0521/0523 08002MPS"""

    taf = parse_taf(taf_text)
    print(f"\n机场: {taf.icao}")
    print(f"发布时间: {taf.issue_time}")
    print(f"有效期: {taf.valid_from} 至 {taf.valid_to}")

    print_weather(taf.initial, "初始天气 (CAVOK)")

    base_date = taf.issue_time.replace(hour=0, minute=0, second=0, microsecond=0)

    test_times = [
        ("10:00", base_date.replace(hour=10)),
        ("13:00", base_date.replace(hour=13)),
        ("17:00", base_date.replace(hour=17)),
        ("22:00", base_date.replace(hour=22)),
    ]

    for time_label, query_time in test_times:
        try:
            weather = get_weather_at_time(taf, query_time)
            print_weather(weather, f"{time_label} 的天气")
        except ValueError as e:
            print(f"\n{time_label}: {e}")


if __name__ == "__main__":
    test_sample1()
    test_sample2()
    print("\n" + "="*80)
    print("测试完成!")
    print("="*80)
