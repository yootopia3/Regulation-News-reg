"""SSL verification matrix probe — Round 6 Phase 1.

One-shot investigation tool. The runtime pipeline does NOT import this module.
Import has zero side effects; all HTTP work happens under ``__main__``.

For each agency in ``config/agencies.json`` this script issues a single
``requests.get(..., verify=True)`` against the relevant target URL(s) and
records the outcome. Results are written to ``logs/ssl_matrix_local.json``
and also printed to stdout as a simple table.

Usage::

    python3 scripts/ssl_matrix_check.py

Design notes:
- fail-soft: a single failing target never aborts the full run.
- de-dup: a scraper whose ``url`` and ``base_url`` point at the same place
  is probed only once.
- gentle: random 0.5–1.0s sleep between calls to avoid hammering sources.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENCIES_JSON = REPO_ROOT / "config" / "agencies.json"
OUTPUT_JSON = REPO_ROOT / "logs" / "ssl_matrix_local.json"

# Keep the import-time footprint minimal — we only pull in the settings
# USER_AGENT inside ``main()`` to avoid any chain of side effects from src/.


def _kst_now_iso() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).isoformat(timespec="seconds")


def _build_targets(agencies: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return a list of probe targets: {code, collection_method, url}.

    - RSS: probe the feed URL itself.
    - scraper: probe both ``url`` (list URL) and ``base_url``; dedupe when equal.
    """
    targets: list[dict[str, str]] = []
    for a in agencies:
        code = a.get("code", "?")
        method = a.get("collection_method", "?")
        url = a.get("url")
        base_url = a.get("base_url")

        if method == "rss":
            if url:
                targets.append({"code": code, "collection_method": method, "url": url})
            continue

        # scraper / sanction-scraper
        seen: set[str] = set()
        for candidate in (url, base_url):
            if candidate and candidate not in seen:
                seen.add(candidate)
                targets.append(
                    {"code": code, "collection_method": method, "url": candidate}
                )
    return targets


def _probe(url: str, user_agent: str, timeout: int = 20) -> dict[str, Any]:
    """Single verify=True probe. Never raises."""
    import requests  # local import — keeps module import side-effect free

    result: dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "elapsed_sec": None,
        "final_url": None,
        "error_type": None,
        "error_msg": None,
    }
    t0 = time.monotonic()
    try:
        resp = requests.get(
            url,
            verify=True,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        )
        result["ok"] = True
        result["status_code"] = resp.status_code
        result["elapsed_sec"] = round(time.monotonic() - t0, 3)
        result["final_url"] = resp.url
    except Exception as exc:  # fail-soft: capture everything
        result["error_type"] = type(exc).__name__
        msg = str(exc)
        result["error_msg"] = (msg[:300] + "…") if len(msg) > 300 else msg
        result["elapsed_sec"] = round(time.monotonic() - t0, 3)
    return result


def _format_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "code",
        "method",
        "ok",
        "status",
        "elapsed",
        "error_type",
        "url",
    ]
    lines = ["\t".join(headers)]
    for r in rows:
        lines.append(
            "\t".join(
                [
                    str(r.get("code", "")),
                    str(r.get("collection_method", "")),
                    str(r.get("ok", "")),
                    str(r.get("status_code", "")),
                    str(r.get("elapsed_sec", "")),
                    str(r.get("error_type") or ""),
                    str(r.get("url", "")),
                ]
            )
        )
    return "\n".join(lines)


def main() -> int:
    # Pull USER_AGENT from the real settings module so the probe mirrors
    # production request headers. Imported inside main() to keep import-time
    # side effects at zero.
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from src.config.settings import USER_AGENT
    except Exception as exc:
        print(f"[warn] could not import src.config.settings.USER_AGENT: {exc}")
        USER_AGENT = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    with open(AGENCIES_JSON, "r", encoding="utf-8") as f:
        agencies = json.load(f)["agencies"]

    targets = _build_targets(agencies)

    results: list[dict[str, Any]] = []
    for i, t in enumerate(targets):
        probe = _probe(t["url"], USER_AGENT)
        row = {**t, **probe}
        results.append(row)
        print(
            f"[{i+1}/{len(targets)}] {t['code']:<16} ok={probe['ok']} "
            f"status={probe['status_code']} err={probe['error_type']}"
        )
        if i < len(targets) - 1:
            time.sleep(random.uniform(0.5, 1.0))

    # Environment snapshot
    import platform
    try:
        import requests as _req
        req_ver = _req.__version__
    except Exception:
        req_ver = "unknown"
    try:
        import certifi
        ca_bundle = certifi.where()
    except Exception:
        ca_bundle = "unknown"

    payload = {
        "run_at_kst": _kst_now_iso(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "requests": req_ver,
            "certifi_ca_bundle": ca_bundle,
        },
        "results": results,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print()
    print(_format_table(results))
    print()
    print(f"wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
