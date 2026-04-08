"""Snapshot tests for `apply_keyword_safeguards`."""

from src.services.analyzer.safeguards import apply_keyword_safeguards


RULES = {
    "high_importance": {
        "keywords": ["인가취소", "영업정지"],
    },
    "medium_importance": {
        "keywords": ["과태료", "시정명령"],
    },
}


class TestApplyKeywordSafeguards:
    def test_high_importance_keyword_boosts_to_five(self):
        assert apply_keyword_safeguards("A은행 인가취소 결정", 2, RULES) == 5

    def test_medium_importance_keyword_boosts_to_four(self):
        assert apply_keyword_safeguards("B사 과태료 부과", 2, RULES) == 4

    def test_no_match_keeps_original_score(self):
        assert apply_keyword_safeguards("일반 보도자료", 3, RULES) == 3

    def test_score_already_above_high_threshold_is_kept(self):
        # Current code only boosts when new_score < 5; otherwise it falls
        # through and ultimately returns the (possibly unchanged) score.
        assert apply_keyword_safeguards("인가취소 관련", 5, RULES) == 5

    def test_score_already_above_medium_threshold_not_lowered(self):
        assert apply_keyword_safeguards("과태료 부과", 5, RULES) == 5

    def test_empty_rules_returns_original_score(self):
        assert apply_keyword_safeguards("아무 제목", 3, {}) == 3
