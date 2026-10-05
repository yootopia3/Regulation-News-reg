"""List-compatible collection results, including failures and partial results."""

from enum import Enum

import requests


class FailureKind(str, Enum):
    CONNECTION = "connection_failed"
    HTTP = "http_failed"
    PARSE = "parse_failed"
    CONFIG = "config_failed"


class CollectionResult(list):
    """Keep the collectors' iterable/list API while retaining error evidence.

    Failures may coexist with items (e.g. page two failed). ``sources`` is
    populated by the RSS aggregator; individual collectors use ``failures``.
    Only bounded categories, never exception bodies or credentials, go into
    the pipeline summary.
    """

    def __init__(self, items=(), *, failures=()):
        super().__init__(items)
        self.failures = list(failures)
        self.sources = {}

    def fail(self, kind):
        if kind not in self.failures:
            self.failures.append(kind)

    @property
    def status(self):
        return "failed" if self.failures else ("success" if self else "empty")


def failure_kind(error):
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return FailureKind.CONNECTION
    if isinstance(error, requests.HTTPError):
        return FailureKind.HTTP
    return FailureKind.PARSE


def has_empty_marker(soup, selectors):
    """Accept only a source-configured empty-state marker, never arbitrary text."""
    selector = selectors.get("empty")
    return bool(selector and soup.select_one(selector))
