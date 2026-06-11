"""Keyword-based safeguards for analyzer scoring."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.config.settings import SAFEGUARD_KEYWORDS_PATH

logger = logging.getLogger(__name__)


def load_safeguard_keywords(path: Optional[Path] = None) -> dict:
    """Load safeguard keyword rules from JSON config.

    Falls back to an empty dict when the file is absent or malformed.
    """
    config_path = path if path is not None else SAFEGUARD_KEYWORDS_PATH
    try:
        if not config_path.exists():
            return {}
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading safeguards: {e}")
        return {}


def apply_keyword_safeguards(title: str, current_score: int, rules: dict) -> int:
    """
    Apply rule-based safeguards to ensure important keywords are not undervalued by AI.
    """
    try:
        new_score = current_score

        # Check High Importance (Score 5)
        for keyword in rules.get('high_importance', {}).get('keywords', []):
            if keyword in title:
                if new_score < 5:
                    logger.info(f"🛡️ Safeguard triggered (High): '{keyword}' found. Boosting score {current_score} -> 5")
                    return 5

        # Check Medium Importance (Score 4)
        for keyword in rules.get('medium_importance', {}).get('keywords', []):
            if keyword in title:
                if new_score < 4:
                    logger.info(f"🛡️ Safeguard triggered (Medium): '{keyword}' found. Boosting score {current_score} -> 4")
                    new_score = 4

        return new_score

    except Exception as e:
        logger.error(f"Error applying safeguards: {e}")
        return current_score


def is_personnel_announcement(title: str, agency_name: str) -> bool:
    """
    Check if the article is a personnel announcement from key agencies.
    Personnel announcements from any agency are HIGH importance.
    """
    # Key agencies - ALL agencies we track
    key_agencies = ['금융감독원', '금융위원회', '기획재정부', '한국은행', '은행연합회', 'FSS', 'FSC', 'MOEF', 'BOK', 'KFB']

    # Personnel-related keywords (expanded)
    personnel_keywords = [
        '인사', '인사발령', '인사이동', '임명', '취임', '발령',
        '임원', '임원 인사', '부원장', '원장', '국장', '실장', '부장', '팀장', '부서장',
        '승진', '전보', '보직', '개편', '조직개편', '조직 개편'
    ]

    # Check if agency is relevant
    is_key_agency = any(agency in agency_name for agency in key_agencies)

    # Check if title contains personnel keywords
    has_personnel_keyword = any(keyword in title for keyword in personnel_keywords)

    return is_key_agency and has_personnel_keyword
