#!/usr/bin/env python3
"""测试 CYMX TAF 报文的 TEMPO 最坏情况"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import parse_taf, get_weather_display_at_time
from datetime import datetime

TAF_CYMX = "TAF CYMX 071740Z 0718/0818 VRB03KT 1/4SM FG VV002 TEMPO 0718/0720 1SM -SHRA -DZ BR BKN004 OVC006 FM072000 16005KT 1SM -DZ BR BKN004 OVC006 TEMPO 0720/0722 3SM BR SCT004 OVC006 FM072200 16005KT 2SM -SHRA BR OVC004 TEMPO 0722/0801 6SM -SHRA BR OVC008 PROB30 0722/0801 VRB20G30KT 1SM TSRA BR BKN002 OVC060CB FM080100 22010G20KT 3SM -SHRA BR OVC006 PROB30 0801/0807 OVC005 FM080700 22012G22KT 4SM -DZ BR OVC008 FM081400 24012G22KT 6SM BR OVC010 RMK NXT FCST BY 080000Z ="

print("=" * 60)
print("测试 CYMX TAF 报文的 TEMPO 解析")
print("=" * 60)

taf = parse_taf(TAF_CYMX)

print(f"\n机场：{taf.icao}")
print(f"发布时间：{taf.issue_time}")
print(f"有效期：{taf.valid_from} 至 {taf.valid_to}")

print(f"\n变化组数量：{len(taf.changes)}")
print("\n所有变化组:")
for i, change in enumerate(taf.changes):
    print(f"\n[{i}] 类型：{change.type}")
    print(f"    时间：{change.from_time} 至 {change.to_time}")
    print(f"    能见度：{change.weather.visibility}")
    print(f"    天气：{change.weather.weather}")
    print(f"    云：{[(c.amount, c.height, c.type) for c in change.weather.clouds]}")
    if change.weather.wind:
        print(f"    风：dir={change.weather.wind.direction}, spd={change.weather.wind.speed}, gust={change.weather.wind.gust}")

# 测试每个小时的 TEMPO 情况
print("\n" + "=" * 60)
print("每小时 TEMPO 最坏情况分析")
print("=" * 60)

from datetime import timedelta

current = taf.valid_from
while current <= taf.valid_to:
    display = get_weather_display_at_time(taf, current)

    if display.tempo_groups:
        print(f"\n{current.strftime('%m-%d %H:00')} - 有 {len(display.tempo_groups)} 个 TEMPO 组生效:")

        for j, group in enumerate(display.tempo_groups):
            print(f"  TEMPO[{j}]: {group.from_time.strftime('%H:%M')}-{group.to_time.strftime('%H:%M')}")
            print(f"    能见度：{group.weather.visibility}m")
            print(f"    天气：{group.weather.weather}")
            print(f"    云：{[(c.amount, c.height) for c in group.weather.clouds]}")

        if display.tempo:
            print(f"  >>> 最坏情况汇总:")
            print(f"      能见度：{display.tempo.visibility}m")
            print(f"      天气：{display.tempo.weather}")
            print(f"      云：{[(c.amount, c.height) for c in display.tempo.clouds]}")
            if display.tempo.wind:
                print(f"      风：{display.tempo.wind.direction}/{display.tempo.wind.speed}m/s (G{display.tempo.wind.gust})")

    current += timedelta(hours=1)
