"""Tests for env-driven Gemini model ID configuration in `src.config.settings`.

Runtime getters (`get_model_filter_id`, `get_model_analyzer_id`,
`get_model_analyzer_fallback`) read env on every call. They are the code
path that `HybridAnalyzer` actually uses, and they must honor values set
by `load_env()` AFTER `src.config.settings` has already been imported.
"""

import subprocess
import sys
import textwrap
from pathlib import Path


def _run_script(code: str, cwd: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def test_get_model_filter_id_default(monkeypatch):
    monkeypatch.delenv("GEMINI_FILTER_MODEL", raising=False)
    from src.config.settings import get_model_filter_id

    assert get_model_filter_id() == "gemini-2.5-flash-lite"


def test_get_model_filter_id_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_FILTER_MODEL", "filter-test")
    from src.config.settings import get_model_filter_id

    assert get_model_filter_id() == "filter-test"


def test_get_model_analyzer_id_default(monkeypatch):
    monkeypatch.delenv("GEMINI_ANALYZER_MODEL", raising=False)
    from src.config.settings import get_model_analyzer_id

    assert get_model_analyzer_id() == "gemini-3-flash-preview"


def test_get_model_analyzer_id_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_ANALYZER_MODEL", "analyzer-test")
    from src.config.settings import get_model_analyzer_id

    assert get_model_analyzer_id() == "analyzer-test"


def test_get_model_analyzer_fallback_default(monkeypatch):
    monkeypatch.delenv("GEMINI_ANALYZER_FALLBACK_MODEL", raising=False)
    from src.config.settings import get_model_analyzer_fallback

    assert get_model_analyzer_fallback() == "gemini-1.5-pro"


def test_get_model_analyzer_fallback_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_ANALYZER_FALLBACK_MODEL", "fallback-test")
    from src.config.settings import get_model_analyzer_fallback

    assert get_model_analyzer_fallback() == "fallback-test"


def test_getters_honor_load_env_called_after_import(tmp_path):
    """Regression test for the Round 2 follow-up fix.

    Previously `HybridAnalyzer` read model IDs from module-level constants
    in `src.config.settings`, which froze at import time -- before
    `HybridAnalyzer.__init__()` got a chance to call `load_env()`. Values
    set in `.env` were therefore silently ignored. The fix introduces
    getter functions that read `os.environ` on every call.

    This test simulates the real runtime order:
      1. Import `src.config.settings` (with no relevant env set).
      2. Call `load_env(path)` on a tmp `.env` file with overrides.
      3. Assert the getters observe the override.
    """
    project_root = Path(__file__).resolve().parents[3]

    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_FILTER_MODEL=filter-from-dotenv\n"
        "GEMINI_ANALYZER_MODEL=analyzer-from-dotenv\n"
        "GEMINI_ANALYZER_FALLBACK_MODEL=fallback-from-dotenv\n",
        encoding="utf-8",
    )

    code = textwrap.dedent(
        f"""
        import os, sys
        for k in (
            'GEMINI_FILTER_MODEL',
            'GEMINI_ANALYZER_MODEL',
            'GEMINI_ANALYZER_FALLBACK_MODEL',
        ):
            os.environ.pop(k, None)

        sys.path.insert(0, {str(project_root)!r})

        from src.config.settings import (
            load_env,
            get_model_filter_id,
            get_model_analyzer_id,
            get_model_analyzer_fallback,
        )

        load_env({str(env_file)!r})

        assert get_model_filter_id() == 'filter-from-dotenv', get_model_filter_id()
        assert get_model_analyzer_id() == 'analyzer-from-dotenv', get_model_analyzer_id()
        assert get_model_analyzer_fallback() == 'fallback-from-dotenv', get_model_analyzer_fallback()
        """
    )

    _run_script(code, cwd=project_root)
