"""Backward-compatible shim.

Original constants now live in `src.config.settings`. This module re-exports
them so legacy imports like `from config import settings` keep working.

No side effects on import (no `load_dotenv` here).
"""

from src.config.settings import *  # noqa: F401,F403
