"""Dashboard dates preserve upstream grouping without inventing publication dates."""
import re
from datetime import datetime, timezone


def display_date(record):
    value = record.get('published_at')
    source = record.get('published_at_source') or 'legacy'
    if record.get('agency') == 'KFB':
        match = re.fullmatch(r'(.+?)\s+(\d{4}[./-]\d{2}[./-]\d{2})(?:\s+\d+)?', record['title'])
        if match:
            day = re.sub(r'[./]', '-', match[2])
            value, source = day + 'T00:00:00+09:00', 'source'
    if not value:
        return dict(display_at=None, display_date_source=None)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or source not in ('source', 'collected_fallback', 'legacy'):
        raise ValueError('Invalid historical display date')
    return dict(display_at=parsed.astimezone(timezone.utc).isoformat(), display_date_source=source)
