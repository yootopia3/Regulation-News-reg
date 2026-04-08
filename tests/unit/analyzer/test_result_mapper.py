"""Snapshot tests for `src.services.analyzer.result_mapper`.

These freeze the current Gemini-raw → internal-dict mapping. Phase 6 and
beyond should not change the key set without updating these tests.
"""

import json

from src.services.analyzer.result_mapper import (
    parse_analyze_response,
    parse_filter_response,
)


ANALYZE_PAYLOAD = {
    "content": {
        "key_points": "summary text",
        "impact_analysis": "impact text",
        "action_items": ["a1", "a2"],
    },
    "importance": {
        "level": "HIGH",
        "score": 5,
    },
    "classification": {
        "risk_tags": ["tag1"],
        "pillars": ["pillar1"],
    },
}

EXPECTED_ANALYZE_KEYS = {
    "summary",
    "impact_analysis",
    "action_items",
    "risk_level",
    "risk_score",
    "risk_tags",
    "pillars",
    "analyzed_by",
}


class TestParseAnalyzeResponse:
    def test_happy_path_maps_to_db_schema(self):
        text = json.dumps(ANALYZE_PAYLOAD)
        result = parse_analyze_response(text, model_name="gemini-test")
        assert result is not None
        assert set(result.keys()) == EXPECTED_ANALYZE_KEYS
        assert result["summary"] == "summary text"
        assert result["impact_analysis"] == "impact text"
        assert result["action_items"] == ["a1", "a2"]
        assert result["risk_level"] == "HIGH"
        assert result["risk_score"] == 5
        assert result["risk_tags"] == ["tag1"]
        assert result["pillars"] == ["pillar1"]
        assert result["analyzed_by"] == "gemini-test"

    def test_strips_markdown_fences(self):
        text = "```json\n" + json.dumps(ANALYZE_PAYLOAD) + "\n```"
        result = parse_analyze_response(text, model_name="m")
        assert result is not None
        assert result["risk_score"] == 5

    def test_unwraps_single_element_list(self):
        # Gemini occasionally wraps the entire response in [ ... ].
        text = json.dumps([ANALYZE_PAYLOAD])
        result = parse_analyze_response(text, model_name="m")
        assert result is not None
        assert result["risk_level"] == "HIGH"

    def test_tolerates_trailing_garbage(self):
        text = json.dumps(ANALYZE_PAYLOAD) + "\n\nstray prose after json"
        result = parse_analyze_response(text, model_name="m")
        assert result is not None
        assert result["summary"] == "summary text"

    def test_returns_none_on_empty(self):
        assert parse_analyze_response("", model_name="m") is None

    def test_returns_none_on_malformed_json(self):
        assert parse_analyze_response("{not json", model_name="m") is None

    def test_returns_none_on_missing_required_section(self):
        bad = {"content": {"key_points": "x", "impact_analysis": "y", "action_items": []}}
        assert parse_analyze_response(json.dumps(bad), model_name="m") is None


class TestParseFilterResponse:
    def test_happy_path_returns_dict(self):
        payload = {
            "is_relevant": True,
            "importance_score": 4,
            "filter_status": "PASS",
        }
        result = parse_filter_response(json.dumps(payload))
        assert result == payload

    def test_returns_none_on_empty(self):
        assert parse_filter_response("") is None

    def test_returns_none_on_malformed(self):
        assert parse_filter_response("garbage{{") is None
