"""Snapshot tests for `src.collectors.date_parser.parse_date`."""

from datetime import datetime

import pytz

from src.collectors.date_parser import KST, parse_date


class TestParseDate:
    def test_parses_yyyymmdd_no_separator(self):
        result = parse_date("20240315")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        # Localized to KST.
        assert result.tzinfo is not None
        assert result.tzinfo.zone == KST.zone

    def test_parses_dashed_date(self):
        result = parse_date("2024-03-15")
        expected = pytz.timezone("Asia/Seoul").localize(datetime(2024, 3, 15))
        assert result == expected

    def test_parses_dotted_date(self):
        result = parse_date("2024.03.15")
        assert result is not None
        assert (result.year, result.month, result.day) == (2024, 3, 15)

    def test_returns_none_on_empty_string(self):
        assert parse_date("") is None

    def test_returns_none_on_garbage(self):
        # Unparseable input — current behavior is to swallow ValueError
        # and return None.
        assert parse_date("not-a-date") is None
