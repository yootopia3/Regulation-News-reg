"""Stable identity for FSC RSS and HTML links to the same official article."""

import re
from urllib.parse import urlsplit, urlunsplit


def canonical_article_url(url):
    parts = urlsplit(url)
    if parts.hostname == 'www.fsc.go.kr' and re.fullmatch(r'/no010101/\d+', parts.path):
        return urlunsplit(('https', 'www.fsc.go.kr', parts.path, '', ''))
    return url
