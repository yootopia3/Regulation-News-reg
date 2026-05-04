import pytest

from src.services.analyzer import hybrid


def test_hybrid_analyzer_fails_before_gemini_client_when_disabled(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "leftover-key")
    monkeypatch.delenv("GEMINI_ENABLED", raising=False)
    monkeypatch.setattr(hybrid, "load_env", lambda: None)

    def fail_if_constructed(_api_key):
        raise AssertionError("GeminiClient must not be constructed when disabled")

    monkeypatch.setattr(hybrid, "GeminiClient", fail_if_constructed)

    with pytest.raises(RuntimeError, match="Gemini analysis is disabled"):
        hybrid.HybridAnalyzer()
