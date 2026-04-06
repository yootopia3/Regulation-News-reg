"""Parsers that convert raw Gemini JSON responses to internal dicts."""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _load_first_json(text: str) -> Any:
    """Decode the first JSON value in ``text`` and ignore any trailing data.

    Gemini occasionally appends extra characters after the closing brace
    (whitespace, stray markdown, or a second JSON fragment). ``json.loads``
    then raises ``Extra data: line N column 1``. ``JSONDecoder.raw_decode``
    returns the first well-formed value plus the offset where it ended, so
    we can tolerate trailing garbage. Leading garbage (e.g. a stray prose
    sentence before the JSON) is handled by searching for the first ``{``
    or ``[``.
    """
    stripped = text.strip()
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(stripped)
        return obj
    except json.JSONDecodeError:
        # Retry after skipping any leading non-JSON prose.
        for i, ch in enumerate(stripped):
            if ch in '{[':
                obj, _end = decoder.raw_decode(stripped[i:])
                return obj
        raise


def parse_filter_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse the Tier 1 gatekeeper JSON response."""
    if not text:
        return None
    try:
        return _load_first_json(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse filter response: {text[:100]}")
        return None


def parse_analyze_response(text: str, model_name: str) -> Optional[Dict[str, Any]]:
    """Parse the Tier 2 analyst JSON response and map to DB schema."""
    if not text:
        return None
    try:
        # Remove Markdown code block markers if present, then tolerate any
        # trailing garbage via _load_first_json.
        clean_text = text.replace('```json', '').replace('```', '').strip()
        data = _load_first_json(clean_text)

        # Transform to DB schema format. ``TypeError`` is caught in addition
        # to ``KeyError`` because Gemini occasionally returns ``content`` /
        # ``importance`` / ``classification`` as a list instead of a dict,
        # which makes ``data["content"]["key_points"]`` raise
        # ``TypeError: list indices must be integers or slices, not str``.
        return {
            "summary": data["content"]["key_points"],
            "impact_analysis": data["content"]["impact_analysis"],
            "action_items": data["content"]["action_items"],
            "risk_level": data["importance"]["level"],
            "risk_score": data["importance"]["score"],
            "risk_tags": data["classification"]["risk_tags"],
            "pillars": data["classification"]["pillars"],
            "analyzed_by": model_name  # Keep track of which model was used
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse analysis response: {e}, Text: {text[:100]}")
        return None
