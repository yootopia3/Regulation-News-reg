"""Gemini SDK wrapper with retry logic."""

import logging
import time
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiClient:
    """Thin wrapper around the Gemini SDK with retry/backoff."""

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def call_json(self, model_name: str, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini API with retry logic. Returns raw JSON string or None."""
        base_delay = 10
        config = types.GenerateContentConfig(
            response_mime_type="application/json"
        )

        for attempt in range(max_retries):
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                text = getattr(response, "text", None)
                if text:
                    return text
                return None

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay = base_delay * (attempt + 1)
                    logger.warning(f"Rate Limit hit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    logger.error(f"Model {model_name} not found")
                    return None
                else:
                    logger.error(f"API Error ({model_name}): {error_str[:200]}")
                    time.sleep(5)

        logger.error("Failed after max retries")
        return None
