"""Regression tests for the GeminiClient SDK wrapper.

Boundaries:
- Mocks are installed against ``src.services.analyzer.gemini_client``'s own
  module-level symbols (``genai``, ``types``, ``time.sleep``), so this suite
  never touches the real ``google.genai`` package, real network, or real
  sleeps.
- No environment variable is read; the API key is a constant string.
"""

import pytest

from src.services.analyzer.gemini_client import GeminiClient


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal stand-in for the SDK response object."""

    def __init__(self, text):
        self.text = text


class FakeConfig:
    """Records the kwargs it was constructed with."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeTypes:
    """Stand-in for ``google.genai.types`` exposing only what wrapper uses."""

    def __init__(self):
        self.config_calls = []

    def GenerateContentConfig(self, **kwargs):  # noqa: N802 - mirror SDK name
        self.config_calls.append(kwargs)
        return FakeConfig(**kwargs)


class FakeModels:
    """Captures generate_content invocations and dispatches a side effect."""

    def __init__(self, side_effects):
        # ``side_effects`` is a list; each entry is either a FakeResponse to
        # return or an Exception instance to raise. The list is consumed in
        # order; if exhausted, the last entry is reused.
        self._side_effects = list(side_effects)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if not self._side_effects:
            raise AssertionError("generate_content called more times than expected")
        effect = self._side_effects.pop(0) if len(self._side_effects) > 1 else self._side_effects[0]
        if isinstance(effect, BaseException):
            raise effect
        return effect


class FakeClient:
    def __init__(self, models):
        self.models = models


class FakeGenai:
    """Stand-in for ``google.genai`` module."""

    def __init__(self, models):
        self._models = models
        self.client_calls = []

    def Client(self, api_key):  # noqa: N802 - mirror SDK name
        self.client_calls.append({"api_key": api_key})
        return FakeClient(self._models)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _install_fakes(monkeypatch, side_effects):
    """Patch the wrapper's module-level symbols and capture sleep calls."""
    models = FakeModels(side_effects)
    fake_genai = FakeGenai(models)
    fake_types = FakeTypes()
    sleep_calls = []

    def _fake_sleep(seconds, *_args, **_kwargs):
        sleep_calls.append(seconds)

    monkeypatch.setattr("src.services.analyzer.gemini_client.genai", fake_genai)
    monkeypatch.setattr("src.services.analyzer.gemini_client.types", fake_types)
    monkeypatch.setattr("src.services.analyzer.gemini_client.time.sleep", _fake_sleep)

    return {
        "models": models,
        "genai": fake_genai,
        "types": fake_types,
        "sleep_calls": sleep_calls,
    }


# ---------------------------------------------------------------------------
# Case 1: success path
# ---------------------------------------------------------------------------


def test_call_json_success_returns_text(monkeypatch):
    fakes = _install_fakes(monkeypatch, [FakeResponse(text='{"ok": 1}')])

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result == '{"ok": 1}'
    assert len(fakes["models"].calls) == 1
    assert len(fakes["sleep_calls"]) == 0


# ---------------------------------------------------------------------------
# Case 2: 429 / RESOURCE_EXHAUSTED retry then success
# ---------------------------------------------------------------------------


def test_call_json_retries_on_resource_exhausted_then_succeeds(monkeypatch):
    fakes = _install_fakes(
        monkeypatch,
        [
            Exception("429 RESOURCE_EXHAUSTED: quota"),
            FakeResponse(text='{"ok": "after-retry"}'),
        ],
    )

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result == '{"ok": "after-retry"}'
    assert len(fakes["models"].calls) == 2
    assert fakes["sleep_calls"] == [10]


# ---------------------------------------------------------------------------
# Case 3: 404 / NOT_FOUND immediate None
# ---------------------------------------------------------------------------


def test_call_json_not_found_returns_none_without_retry(monkeypatch):
    fakes = _install_fakes(monkeypatch, [Exception("404 NOT_FOUND: model xyz")])

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result is None
    assert len(fakes["models"].calls) == 1
    assert len(fakes["sleep_calls"]) == 0


# ---------------------------------------------------------------------------
# Case 4: other exceptions exhaust max_retries → None
# ---------------------------------------------------------------------------


def test_call_json_other_exception_exhausts_max_retries_returns_none(monkeypatch):
    fakes = _install_fakes(monkeypatch, [Exception("503 INTERNAL ERROR")])

    client = GeminiClient("fake-api-key")
    result = client.call_json("model", "prompt", max_retries=3)

    assert result is None
    assert len(fakes["models"].calls) == 3
    assert fakes["sleep_calls"] == [5, 5, 5]


# ---------------------------------------------------------------------------
# Case 5: response.text missing/empty → None
# ---------------------------------------------------------------------------


def test_call_json_returns_none_when_response_text_is_none(monkeypatch):
    fakes = _install_fakes(monkeypatch, [FakeResponse(text=None)])

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result is None
    assert len(fakes["models"].calls) == 1
    assert len(fakes["sleep_calls"]) == 0


def test_call_json_returns_none_when_response_text_is_empty_string(monkeypatch):
    fakes = _install_fakes(monkeypatch, [FakeResponse(text="")])

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result is None
    assert len(fakes["models"].calls) == 1
    assert len(fakes["sleep_calls"]) == 0


# ---------------------------------------------------------------------------
# Case 6: GenerateContentConfig kwargs are forwarded correctly
# ---------------------------------------------------------------------------


def test_call_json_forwards_model_prompt_and_json_config(monkeypatch):
    fakes = _install_fakes(monkeypatch, [FakeResponse(text='{"ok": 1}')])

    client = GeminiClient("fake-api-key")
    client.call_json("gemini-test-model", "prompt text")

    assert len(fakes["models"].calls) == 1
    call_kwargs = fakes["models"].calls[0]
    assert call_kwargs["model"] == "gemini-test-model"
    assert call_kwargs["contents"] == "prompt text"
    assert call_kwargs["config"].response_mime_type == "application/json"

    assert fakes["types"].config_calls == [{"response_mime_type": "application/json"}]


# ---------------------------------------------------------------------------
# Case 7: hybrid contract — failure path returns *exactly* None (identity)
# ---------------------------------------------------------------------------


def test_call_json_failure_returns_none_identity_for_hybrid_contract(monkeypatch):
    """``hybrid.py`` relies on ``if not response_text:`` against a None.

    This test pins the identity (not just falsiness) of the failure-path
    return value so the hybrid fallback contract cannot silently regress to a
    different falsy sentinel like ``False``, ``0``, or ``""``.
    """
    _install_fakes(monkeypatch, [Exception("404 NOT_FOUND: model abc")])

    client = GeminiClient("fake-api-key")
    result = client.call_json("gemini-test-model", "prompt text")

    assert result is None
    assert result is not False
    assert result != 0
    assert result != ""
