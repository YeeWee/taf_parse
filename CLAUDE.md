# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TAF (Terminal Aerodrome Forecast) parser for aviation weather data. Converts raw TAF meteorological reports into structured data.

**Core functionality:**
- Input: Airport TAF report + query time
- Output: Weather conditions at the specified time

## Commands

```bash
# Run web interface
streamlit run app.py

# Run command-line examples
python example.py

# Run tests
pytest tests/

# Run single test
pytest tests/test_parser.py::TestTAFParser::test_parse_basic_taf

# Install dependencies
pip install -r requirements.txt
```

## Architecture

```
taf_parse/
├── app.py                 # Streamlit web application
├── example.py             # Command-line usage examples
├── src/
│   ├── parser.py          # Core TAF parsing logic
│   ├── models.py          # Pydantic data models
│   ├── utils.py           # Utilities (time parsing, Chinese translation)
│   └── validator.py       # Data validation
├── tests/
│   ├── test_parser.py     # Unit tests
│   └── test_integration.py # Integration tests
└── docs/                  # TAF format documentation
```

## Key Components

**Data Models (`src/models.py`):**
- `TAF` - Complete weather forecast
- `WeatherState` - Wind, visibility, weather phenomena, clouds
- `ChangeGroup` - FM/BECMG/TEMPO/PROB change groups
- `TAFDisplay` - Display data with main weather and TEMPO separated

**Parser (`src/parser.py`):**
- `parse_taf()` - Parse raw TAF text into structured data
- `get_weather_at_time()` - Get weather at specific query time
- `get_weather_display_at_time()` - Get display data with TEMPO details separated

**Supported TAF formats:**
- Standard (China/International)
- TAF AMD (amended), TAF COR (corrected)
- FMDDHHMM format (FM change group with time)
- Imperial units (SM visibility, KT wind speed)
- 24-hour format (day boundary handling)
- WMO headers (e.g., FTUS31 KWBC 071740)

## Short-Term Forecast Handling (TEMPO/INTER/PROB)

All short-term forecast types are treated equally. When time periods overlap, the worst case is used for aviation safety dispatch:

**Supported Types:**
- `TEMPO` - Temporary changes
- `INTER` - Intermittent changes
- `PROBxx` - Probability forecast (PROB30, PROB40, etc.)
- `PROBxx TEMPO` - Probabilistic temporary changes
- `PROBxx INTER` - Probabilistic intermittent changes
- `INTER PROBxx` - Intermittent probabilistic changes

**Worst Case Aggregation:**
- Visibility: minimum value
- Cloud base: lowest height (regardless of cloud amount)
- Wind: maximum speed/gust
- Weather phenomena: sorted by severity, deduplicated

**Severity Ranking (high to low):**
1. Thunderstorm + precipitation/hail (TSGR, TSRA, TSSN)
2. Sandstorm/dust storm (SS, DS)
3. Freezing rain (FZRA, FZDZ)
4. Hail (GR, GS)
5. Showers (SHRA, SHSN)
6. Precipitation (RA, SN)
7. Fog (FG)
8. Mist/haze (BR, HZ)

**Example:**
```
05:00 - TEMPO (RA), INTER (-RA), PROB30 TEMPO (TSRA) overlap
Result: TSRA (thunderstorm with rain) is the worst case
```

## Testing Notes

The test suite in `tests/test_parser.py` has several skipped tests marked `@pytest.mark.skip(reason="待实现")` for CAVOK, TEMPO, and PROB parsing that need implementation.
