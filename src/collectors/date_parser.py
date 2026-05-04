"""Date parsing helpers for scraper modules (KST-aware)."""

import re
from datetime import datetime
from typing import Optional

import pytz


KST = pytz.timezone('Asia/Seoul')

TIME_RE = re.compile(r'(?<!\d)([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?')


def has_specific_time(date_str: str) -> bool:
    """Return True when the source string includes a non-midnight time."""
    if not date_str:
        return False

    match = TIME_RE.search(date_str)
    if not match:
        return False

    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    return any((hour, minute, second))


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date string formats and localize to KST.

    Supported formats:
        - YYYYMMDD (no separator, used by FSS sanction notices)
        - YYYY-MM-DD or YYYY.MM.DD
    """
    if not date_str:
        return None

    try:
        # Try format: YYYYMMDD (no separator, used by FSS sanction notices)
        match_no_sep = re.search(r'^(\d{8})$', date_str.strip())
        if match_no_sep:
            dt = datetime.strptime(match_no_sep.group(1), '%Y%m%d')
            return KST.localize(dt)

        # Try format: YYYY-MM-DD or YYYY.MM.DD
        match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)

        if match:
            clean_date_str = match.group(1).replace('.', '-')
        else:
            clean_date_str = date_str.strip().replace('.', '-')

        dt = datetime.strptime(clean_date_str, '%Y-%m-%d')
        return KST.localize(dt)

    except ValueError:
        return None
