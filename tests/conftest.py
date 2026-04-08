"""Shared pytest configuration for the reg_brief test suite."""

import os
import sys
from pathlib import Path

# Ensure project root is at sys.path[0] so `from src...` imports work for
# every test, regardless of pytest's invocation directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

# Defensive env isolation: even though no test in this suite reads secrets,
# scrub them at import time so an accidental network/SDK call cannot
# authenticate using developer-machine credentials.
for _var in ("GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"):
    os.environ.pop(_var, None)
