"""Snapshot tests for `extract_sanction_key`.

This is the seed for Phase 6 (sanction-rule-derivation).
"""

from src.collectors.sanction_scraper import extract_sanction_key


class TestExtractSanctionKey:
    def test_extracts_both_ids_from_full_query(self):
        link = (
            "https://www.fss.or.kr/fss/bbs/B0000188/view.do"
            "?examMgmtNo=2024001&emOpenSeq=42&menuNo=200218"
        )
        assert extract_sanction_key(link) == ("2024001", "42")

    def test_returns_none_pair_when_query_missing(self):
        # PDF download link with no examMgmtNo / emOpenSeq pair.
        link = "https://www.fss.or.kr/fss/cmm/fms/FileDown.do?atchFileId=abc"
        assert extract_sanction_key(link) == (None, None)

    def test_partial_query_returns_partial_pair(self):
        # Only examMgmtNo is present — current code returns the missing
        # field as None rather than failing.
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?examMgmtNo=2024001"
        assert extract_sanction_key(link) == ("2024001", None)

    def test_url_with_no_query_returns_none_pair(self):
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do"
        assert extract_sanction_key(link) == (None, None)
