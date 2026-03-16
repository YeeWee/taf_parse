"""
TAF 解析器测试
"""

import pytest
from src.parser import parse_taf


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

    @pytest.mark.skip(reason="待实现")
    def test_parse_cavok(self):
        """测试解析 CAVOK"""
        pass

    @pytest.mark.skip(reason="待实现")
    def test_parse_tempo(self):
        """测试解析 TEMPO 组"""
        pass

    @pytest.mark.skip(reason="待实现")
    def test_parse_prob(self):
        """测试解析 PROB 组"""
        pass
