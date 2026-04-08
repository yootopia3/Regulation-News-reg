"""Tests for env-driven Gemini model ID configuration in `src.config.settings`.

Two layers are covered:

1. Legacy module-level constants (`MODEL_FILTER_ID`, `MODEL_ANALYZER_ID`,
   `MODEL_ANALYZER_FALLBACK`) are read at import time. These preserve
   backward compatibility and are tested in fresh subprocesses where env
   is pre-set before the import.

2. Runtime getters (`get_model_filter_id`, `get_model_analyzer_id`,
   `get_model_analyzer_fallback`) read env on every call. These are the
   code path that `HybridAnalyzer` actually uses, and they must honor
   values set by `load_env()` AFTER `src.config.settings` has already
   been imported. This layer is tested by writing a temporary `.env`
   file in a subprocess, importing settings first (with no override in
   the process environment), calling `load_env(path)`, then asserting
   the getters return the override.
"""

import subprocess
import sys
import textwrap
from pathlib import Path


def _run(env_assignments: str, assertions: str) -> None:
    code = (
        "import os\n"
        f"{env_assignments}\n"
        "from src.config.settings import (\n"
        "    MODEL_FILTER_ID, MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK\n"
        ")\n"
        f"{assertions}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


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


def test_model_ids_default_when_env_unset():
    _run(
        env_assignments=(
            "for k in ('GEMINI_FILTER_MODEL','GEMINI_ANALYZER_MODEL',"
            "'GEMINI_ANALYZER_FALLBACK_MODEL'):\n"
            "    os.environ.pop(k, None)"
        ),
        assertions=(
            "assert MODEL_FILTER_ID == 'gemini-2.5-flash-lite'\n"
            "assert MODEL_ANALYZER_ID == 'gemini-3-flash-preview'\n"
            "assert MODEL_ANALYZER_FALLBACK == 'gemini-1.5-pro'"
        ),
    )


def test_model_ids_overridden_by_env():
    _run(
        env_assignments=(
            "os.environ['GEMINI_FILTER_MODEL'] = 'filter-test'\n"
            "os.environ['GEMINI_ANALYZER_MODEL'] = 'analyzer-test'\n"
            "os.environ['GEMINI_ANALYZER_FALLBACK_MODEL'] = 'fallback-test'"
        ),
        assertions=(
            "assert MODEL_FILTER_ID == 'filter-test'\n"
            "assert MODEL_ANALYZER_ID == 'analyzer-test'\n"
            "assert MODEL_ANALYZER_FALLBACK == 'fallback-test'"
        ),
    )


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

    The project root is detected as the parent of the tests directory.
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
        # Ensure no pre-existing override in the subprocess env so we are
        # exercising the `.env` path, not the outer shell env.
        for k in (
            'GEMINI_FILTER_MODEL',
            'GEMINI_ANALYZER_MODEL',
            'GEMINI_ANALYZER_FALLBACK_MODEL',
        ):
            os.environ.pop(k, None)

        sys.path.insert(0, {str(project_root)!r})

        # Import settings FIRST (freezes legacy constants to defaults).
        from src.config.settings import (
            load_env,
            get_model_filter_id,
            get_model_analyzer_id,
            get_model_analyzer_fallback,
        )

        # Then load .env (this is the order HybridAnalyzer.__init__ uses).
        load_env({str(env_file)!r})

        assert get_model_filter_id() == 'filter-from-dotenv', get_model_filter_id()
        assert get_model_analyzer_id() == 'analyzer-from-dotenv', get_model_analyzer_id()
        assert get_model_analyzer_fallback() == 'fallback-from-dotenv', get_model_analyzer_fallback()
        """
    )

    _run_script(code, cwd=project_root)


def test_getters_return_defaults_when_env_unset(tmp_path):
    """Getters must fall back to hardcoded defaults when no env is set."""
    project_root = Path(__file__).resolve().parents[3]

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
            get_model_filter_id,
            get_model_analyzer_id,
            get_model_analyzer_fallback,
        )

        assert get_model_filter_id() == 'gemini-2.5-flash-lite'
        assert get_model_analyzer_id() == 'gemini-3-flash-preview'
        assert get_model_analyzer_fallback() == 'gemini-1.5-pro'
        """
    )

    _run_script(code, cwd=project_root)
