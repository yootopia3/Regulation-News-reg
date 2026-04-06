"""HTTP session and fetch helpers for collectors.

Provides a lazily-created, module-level `requests.Session` with the standard
scraper headers, and a `fetch()` helper that applies default timeout and
SSL verification from settings.
"""

from typing import Optional

import requests

from src.config import settings


_DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

_session: Optional[requests.Session] = None
_ssl_warnings_suppressed: bool = False


def _maybe_suppress_ssl_warnings() -> None:
    global _ssl_warnings_suppressed
    if _ssl_warnings_suppressed:
        return
    if settings.SUPPRESS_SSL_WARNINGS:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _ssl_warnings_suppressed = True


def get_session() -> requests.Session:
    """Return the cached module-level Session, creating it on first call."""
    global _session
    if _session is None:
        _maybe_suppress_ssl_warnings()
        session = requests.Session()
        session.headers.update(_DEFAULT_HEADERS)
        _session = session
    return _session


def fetch(url: str, *, timeout: Optional[int] = None) -> requests.Response:
    """Perform a GET request via the cached session with standard defaults."""
    response = get_session().get(
        url,
        timeout=timeout or settings.SCRAPER_TIMEOUT,
        verify=settings.SSL_VERIFY,
    )
    response.raise_for_status()
    return response
