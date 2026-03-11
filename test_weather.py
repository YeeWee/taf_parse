#!/usr/bin/env python3
"""测试 is_weather_token 对 PROB30 的识别"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser import is_weather_token

test_tokens = ['PROB30', 'PROB', 'TSRA', 'BR', 'VRB20G30KT', 'OVC005']

for token in test_tokens:
    result = is_weather_token(token)
    print(f"is_weather_token('{token}') = {result}")
