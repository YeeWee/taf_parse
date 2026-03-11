#!/usr/bin/env python3
"""调试 PROB30 解析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import parse_change_group
from datetime import datetime

# 模拟 token 流：PROB30 0722/0801 VRB20G30KT 1SM TSRA BR BKN002 OVC060CB
tokens = ['PROB30', '0722/0801', 'VRB20G30KT', '1SM', 'TSRA', 'BR', 'BKN002', 'OVC060CB', 'FM080100']

base_date = datetime(2026, 3, 7, 17, 40)
valid_from = datetime(2026, 3, 7, 18, 0)
valid_to = datetime(2026, 3, 8, 18, 0)

token_iter = iter(tokens[1:])  # 跳过第一个 PROB30

change_group, remaining = parse_change_group('PROB30', token_iter, base_date, valid_from, valid_to)

print(f"解析结果:")
print(f"  type: {change_group.type}")
print(f"  probability: {change_group.probability}")
print(f"  from_time: {change_group.from_time}")
print(f"  to_time: {change_group.to_time}")
print(f"  weather.visibility: {change_group.weather.visibility}")
print(f"  weather.weather: {change_group.weather.weather}")
print(f"  remaining: {remaining}")
