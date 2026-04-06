"""Pagination URL builders for list scraping."""

import re


def build_page_url(base_url: str, page: int) -> str:
    """Build the URL for a given page number.

    FSC uses `curPage`, other agencies use `pageIndex`.
    """
    if "fsc.go.kr" in base_url:
        page_param = f"curPage={page}"
        sep = "&" if "?" in base_url else "?"
        if "curPage=" in base_url:
            return re.sub(r'curPage=\d+', page_param, base_url)
        return f"{base_url}{sep}{page_param}"

    page_param = f"pageIndex={page}"
    sep = "&" if "?" in base_url else "?"
    if "pageIndex=" in base_url:
        return re.sub(r'pageIndex=\d+', page_param, base_url)
    return f"{base_url}{sep}{page_param}"
