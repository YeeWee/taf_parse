#!/usr/bin/env python3
"""检查所有 token 识别函数"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import is_weather_token, is_visibility_token, is_wind_token, is_cloud_token

test_tokens = ['PROB30', 'PROB', '0722/0801', '1SM', 'VRB20G30KT']

print("Token 识别测试:\n")
for token in test_tokens:
    weather = is_weather_token(token)
    vis = is_visibility_token(token)
    wind = is_wind_token(token)
    cloud = is_cloud_token(token)
    print(f"{token}:")
    print(f"  is_weather_token: {weather}")
    print(f"  is_visibility_token: {vis}")
    print(f"  is_wind_token: {wind}")
    print(f"  is_cloud_token: {cloud}")
    print()
