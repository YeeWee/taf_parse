#!/usr/bin/env python3
"""详细测试 is_weather_token"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import is_weather_token

# 测试所有可能的 token
test_tokens = [
    'PROB30', 'PROB40', 'PROB',
    '-SHRA', 'BR', 'TSRA',
    'VRB20G30KT', 'OVC008', 'BKN002',
    '1SM', '6SM',
]

print("测试 is_weather_token:")
for token in test_tokens:
    result = is_weather_token(token)
    print(f"  {token}: {result}")

# 检查天气前缀匹配逻辑
print("\n检查天气前缀匹配:")
test_token = 'PROB30'
weather_prefixes = ('-', '+', 'VC', 'RE', 'MI', 'PR', 'BC', 'DR', 'BL', 'SH', 'TS', 'FZ')

test_token_stripped = test_token.lstrip('+-')
print(f"test_token: {test_token}")
print(f"after strip: {test_token_stripped}")

for prefix in weather_prefixes:
    if test_token_stripped.startswith(prefix):
        print(f"  匹配前缀：{prefix}")
        if prefix == 'PR':
            print(f"    PR 是天气前缀 (降水类/高吹类)")
