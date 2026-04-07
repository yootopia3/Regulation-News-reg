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


def _unwrap_if_list(obj: Any) -> Any:
    """Return the first element if ``obj`` is a non-empty list, else ``obj``.

    Gemini occasionally wraps the analysis response (or one of its sections)
    in a single-element JSON array — e.g. ``[{...}]`` instead of ``{...}``,
    or ``"content": [{...}]`` instead of ``"content": {...}``. The downstream
    code expects dict access, so unwrap once at each level we touch.
    Returns ``obj`` unchanged for any other type.
    """
    if isinstance(obj, list) and obj:
        return obj[0]
    return obj


def parse_analyze_response(text: str, model_name: str) -> Optional[Dict[str, Any]]:
    """Parse the Tier 2 analyst JSON response and map to DB schema."""
    if not text:
        return None
    try:
        # Remove Markdown code block markers if present, then tolerate any
        # trailing garbage via _load_first_json.
        clean_text = text.replace('```json', '').replace('```', '').strip()
        data = _load_first_json(clean_text)

        # Tolerate Gemini wrapping the whole response in a single-element
        # array. Without this, ``data["content"]`` raises
        # ``TypeError: list indices must be integers or slices, not str``
        # and the analysis silently degrades to ANALYSIS_FAILED.
        data = _unwrap_if_list(data)
        if not isinstance(data, dict):
            logger.error(
                f"Unexpected analysis response type {type(data).__name__}, "
                f"Text: {text[:100]}"
            )
            return None

        # Same defensive unwrap for each top-level section, in case Gemini
        # wraps a section instead of (or in addition to) the root.
        content = _unwrap_if_list(data.get("content", {}))
        importance = _unwrap_if_list(data.get("importance", {}))
        classification = _unwrap_if_list(data.get("classification", {}))

        # Transform to DB schema format. KeyError/TypeError still caught for
        # genuinely malformed responses (missing required keys, wrong nested
        # shapes the unwrap above can't fix).
        return {
            "summary": content["key_points"],
            "impact_analysis": content["impact_analysis"],
            "action_items": content["action_items"],
            "risk_level": importance["level"],
            "risk_score": importance["score"],
            "risk_tags": classification["risk_tags"],
            "pillars": classification["pillars"],
            "analyzed_by": model_name  # Keep track of which model was used
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse analysis response: {e}, Text: {text[:100]}")
        return None
