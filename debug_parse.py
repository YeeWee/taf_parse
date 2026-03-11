#!/usr/bin/env python3
"""详细调试 TEMPO 0722/0801 的解析过程"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 修改 parse_change_group 来添加调试输出
from parser import parse_taf, parse_change_group, parse_ddhhddhh
from datetime import datetime

# 模拟 token 流
# TEMPO 0722/0801 6SM -SHRA BR OVC008 PROB30 0722/0801 VRB20G30KT 1SM TSRA BR BKN002 OVC060CB

tokens = ['TEMPO', '0722/0801', '6SM', '-SHRA', 'BR', 'OVC008',
          'PROB30', '0722/0801', 'VRB20G30KT', '1SM', 'TSRA', 'BR', 'BKN002', 'OVC060CB',
          'FM080100']

base_date = datetime(2026, 3, 7, 17, 40)
valid_from = datetime(2026, 3, 7, 18, 0)
valid_to = datetime(2026, 3, 8, 18, 0)

token_iter = iter(tokens)
first_token = next(token_iter)  # 'TEMPO'

print(f"解析第一个 token: {first_token}")
print(f"剩余 tokens: {list(token_iter)}")

# 重新创建迭代器
token_iter = iter(tokens[1:])

change_group, remaining = parse_change_group(first_token, token_iter, base_date, valid_from, valid_to)

print(f"\n解析结果:")
print(f"  type: {change_group.type}")
print(f"  probability: {change_group.probability}")
print(f"  from_time: {change_group.from_time}")
print(f"  to_time: {change_group.to_time}")
print(f"  weather.visibility: {change_group.weather.visibility}")
print(f"  weather.weather: {change_group.weather.weather}")
print(f"  weather.clouds: {[(c.amount, c.height, c.type) for c in change_group.weather.clouds]}")
print(f"  remaining tokens: {remaining}")
