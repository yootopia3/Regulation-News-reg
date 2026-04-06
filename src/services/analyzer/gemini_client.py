"""Gemini SDK wrapper with retry logic."""

import logging
import time
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

logger = logging.getLogger(__name__)


class GeminiClient:
    """Thin wrapper around the Gemini SDK with retry/backoff."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def call_json(self, model_name: str, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini API with retry logic."""
        base_delay = 10
        model = genai.GenerativeModel(model_name)

        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=GenerationConfig(
                        response_mime_type="application/json"
                    )
                )

                if response.text:
                    return response.text
                return None

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay = base_delay * (attempt + 1)
                    logger.warning(f"Rate Limit hit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    logger.error(f"Model {model_name} not found")
                    # Fallback instantly if model name is wrong
                    return None
                else:
                    logger.error(f"API Error ({model_name}): {error_str[:200]}")
                    # If it's a critical error, maybe don't retry immediately or handle differently
                    # But for now, we try/catch loop
                    time.sleep(5)

        logger.error("Failed after max retries")
        return None
