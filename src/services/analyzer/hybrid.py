"""HybridAnalyzer orchestrator: Gatekeeper + Analyst pipeline."""

import logging
import time
from typing import Any, Dict, Optional

from src.config.settings import (
    API_CALL_DELAY,
    IMPORTANCE_THRESHOLD,
    get_gemini_api_key,
    get_model_analyzer_fallback,
    get_model_analyzer_id,
    get_model_filter_id,
    load_env,
)
from src.services.analyzer.gemini_client import GeminiClient
from src.services.analyzer.prompts import build_analyze_prompt, build_filter_prompt
from src.services.analyzer.result_mapper import (
    parse_analyze_response,
    parse_filter_response,
)
from src.services.analyzer.safeguards import (
    apply_keyword_safeguards,
    load_safeguard_keywords,
)

logger = logging.getLogger(__name__)


class HybridAnalyzer:
    """2-Tier Hybrid Analyzer with Gatekeeper + Analyst pipeline."""

    def __init__(self):
        # load_env() must run BEFORE reading model IDs so that values from
        # `.env` actually take effect. The model IDs are read via getters
        # (not module-level constants), because the constants in
        # `src.config.settings` freeze at import time, which happens above
        # this call and thus predates `.env` loading.
        load_env()
        self._client = GeminiClient(get_gemini_api_key())
        self._safeguard_rules = load_safeguard_keywords()

        self.filter_model = get_model_filter_id()
        self.analyzer_model = get_model_analyzer_id()
        self.analyzer_fallback = get_model_analyzer_fallback()
        self.importance_threshold = IMPORTANCE_THRESHOLD

    def filter(self, title: str, description: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 1: Gatekeeper - Quick relevance filtering.
        Uses only title + description to save tokens.
        """
        prompt = build_filter_prompt(title, description, agency_name)
        response_text = self._client.call_json(self.filter_model, prompt)
        return parse_filter_response(response_text) if response_text else None

    def analyze(self, title: str, full_content: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 2: Analyst - Deep analysis for important news.
        Uses full article content.
        """
        prompt = build_analyze_prompt(title, full_content, agency_name)

        # Try primary model
        response_text = self._client.call_json(self.analyzer_model, prompt)

        # Fallback if primary fails
        if not response_text:
            logger.warning(f"Primary model {self.analyzer_model} failed. Trying fallback {self.analyzer_fallback}")
            response_text = self._client.call_json(self.analyzer_fallback, prompt)

        if response_text:
            return parse_analyze_response(response_text, self.analyzer_model)
        return None

    def process(self, article: Dict[str, Any], agency_name: str, category: str = 'press_release') -> Dict[str, Any]:
        """
        Main pipeline: Filter -> Analyze (if important)

        Returns combined result with filter and analysis data.
        """
        title = article.get('title', '')
        description = article.get('description') or article.get('content', '')[:200] or title
        full_content = article.get('content') or title

        # Default values
        is_relevant = False
        importance_score = 0
        filter_status = "OK"

        # Step 1: Gatekeeper
        filter_result = self.filter(title, description, agency_name)
        time.sleep(API_CALL_DELAY)  # Rate limit protection

        if filter_result:
            is_relevant = filter_result.get('is_relevant', False)
            importance_score = filter_result.get('importance_score', 0)
        else:
            logger.warning(f"Filter failed for: {title[:50]}")
            filter_status = "ERROR"

        # 🛡️ Apply Keyword Safeguards (Override AI Score)
        original_score = importance_score
        importance_score = apply_keyword_safeguards(title, original_score, self._safeguard_rules)

        # If score was boosted, ensure it's marked as relevant
        if importance_score > original_score:
            is_relevant = True

        # Build result
        result = {
            "is_relevant": is_relevant,
            "importance_score": importance_score,
            "filter_status": filter_status
        }

        # Step 2: Analyst (only for important news)
        # Check if score is high enough (Threshold is usually 3)
        if is_relevant and importance_score >= self.importance_threshold:
            logger.info(f"Proceeding to Tier 2 analysis (Score: {importance_score}): {title[:40]}...")

            analysis = self.analyze(title, full_content, agency_name)
            time.sleep(API_CALL_DELAY)  # Rate limit protection

            if analysis:
                result.update(analysis)
                result["analysis_status"] = "ANALYZED"

                # If safeguard boosted complexity, ensure risk_score matches
                if result.get("risk_score", 0) < importance_score:
                    result["risk_score"] = importance_score
                    if importance_score >= 5:
                        result["risk_level"] = "High"
                    elif importance_score == 4:
                         # Don't downgrade High to Medium, but upgrade Low to Medium
                        if result.get("risk_level") == "Low":
                            result["risk_level"] = "Medium"

                logger.info(f"Analyzed successfully (Model: {self.analyzer_model}): {title[:40]}")
            else:
                result["analysis_status"] = "ANALYSIS_FAILED"
                logger.warning(f"Analysis failed: {title[:40]}")
        else:
            result["analysis_status"] = "SKIPPED"
            logger.info(f"Filtered out (Score: {importance_score}, Relevant: {is_relevant}): {title[:40]}")

        return result
