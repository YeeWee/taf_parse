#!/usr/bin/env python3
"""调试 PROB30 解析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import parse_taf

TAF_CYMX = "TAF CYMX 071740Z 0718/0818 VRB03KT 1/4SM FG VV002 TEMPO 0718/0720 1SM -SHRA -DZ BR BKN004 OVC006 FM072000 16005KT 1SM -DZ BR BKN004 OVC006 TEMPO 0720/0722 3SM BR SCT004 OVC006 FM072200 16005KT 2SM -SHRA BR OVC004 TEMPO 0722/0801 6SM -SHRA BR OVC008 PROB30 0722/0801 VRB20G30KT 1SM TSRA BR BKN002 OVC060CB FM080100 22010G20KT 3SM -SHRA BR OVC006 PROB30 0801/0807 OVC005 FM080700 22012G22KT 4SM -DZ BR OVC008 FM081400 24012G22KT 6SM BR OVC010 RMK NXT FCST BY 080000Z ="

taf = parse_taf(TAF_CYMX)

print("所有变化组类型:")
for i, change in enumerate(taf.changes):
    print(f"[{i}] type='{change.type}', probability={change.probability}")
    print(f"    from={change.from_time}, to={change.to_time}")
    print(f"    weather.visibility={change.weather.visibility}")
    print(f"    weather.weather={change.weather.weather}")
