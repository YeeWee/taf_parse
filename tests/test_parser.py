"""
TAF 解析器测试
"""

import pytest
from src.parser import parse_taf, get_weather_display_at_time


class TestTAFParser:
    """TAF 解析器测试"""

    def test_parse_basic_taf(self):
        """测试解析基本 TAF"""
        taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030"""
        result = parse_taf(taf_text)
        assert result.icao == "ZBAA"

    def test_parse_taf_with_changes(self):
        """测试解析带变化组的 TAF"""
        taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS 6000 SCT030
BECMG 0514/0516 32010G18MPS 3000 SHRA BKN010"""
        result = parse_taf(taf_text)
        assert result is not None

    def test_parse_cavok(self):
        """测试解析 CAVOK"""
        taf_text = """TAF ZBAA 051100Z 0512/0618 18004MPS CAVOK"""
        result = parse_taf(taf_text)
        assert result.initial.cavok is True
        assert result.initial.visibility == 10000  # CAVOK 时能见度视为 10000 米

    def test_cavok_to_becmg_deterioration(self):
        """测试 CAVOK 后接 BECMG 能见度变差的较差值逻辑"""
        taf_text = """TAF RKSS 150500Z 1506/1612 26006KT CAVOK TNM02/1522Z TX12/1606Z
BECMG 1518/1520 32005KT 4000 BR NSC BECMG 1521/1523 29006KT CAVOK="""
        result = parse_taf(taf_text)

        # 初始天气为 CAVOK
        assert result.initial.cavok is True

        # 第一个 BECMG：能见度变差，应清除 CAVOK
        becmg1 = result.changes[0]
        assert becmg1.weather.cavok is False
        assert becmg1.weather.visibility == 4000
        assert 'BR' in becmg1.weather.weather

        # 第二个 BECMG：恢复 CAVOK
        becmg2 = result.changes[1]
        assert becmg2.weather.cavok is True
        assert becmg2.weather.visibility == 10000
        assert len(becmg2.weather.weather) == 0

        # 验证各时间点的查询结果
        from datetime import datetime

        # 17:00（BECMG 前一刻）：应保持 CAVOK
        display_before = get_weather_display_at_time(result, datetime(2026, 4, 15, 17, 0))
        assert display_before.main.cavok is True

        # 18:00-20:00（BECMG 期间）：应显示较差值（4000 米，BR）
        for hour in [18, 19, 20]:
            display = get_weather_display_at_time(result, datetime(2026, 4, 15, hour, 0))
            assert display.main.cavok is False, f"{hour}:00 CAVOK 应在 BECMG 期间清除"
            assert display.main.visibility == 4000, f"{hour}:00 能见度应为 4000 米"
            assert 'BR' in display.main.weather, f"{hour}:00 应包含 BR 天气现象"

        # 23:00（BECMG 到 CAVOK 完成）：应恢复 CAVOK
        display_after = get_weather_display_at_time(result, datetime(2026, 4, 15, 23, 0))
        assert display_after.main.cavok is True

    @pytest.mark.skip(reason="待实现")
    def test_parse_tempo(self):
        """测试解析 TEMPO 组"""
        pass

    @pytest.mark.skip(reason="待实现")
    def test_parse_prob(self):
        """测试解析 PROB 组"""
        pass
