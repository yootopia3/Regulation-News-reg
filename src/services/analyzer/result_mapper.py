"""Parsers that convert raw Gemini JSON responses to internal dicts."""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def parse_filter_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse the Tier 1 gatekeeper JSON response."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse filter response: {text[:100]}")
        return None


def parse_analyze_response(text: str, model_name: str) -> Optional[Dict[str, Any]]:
    """Parse the Tier 2 analyst JSON response and map to DB schema."""
    if not text:
        return None
    try:
        # Remove Markdown code block if present
        clean_text = text.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_text)

        # Transform to DB schema format
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
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse analysis response: {e}, Text: {text[:100]}")
        return None
