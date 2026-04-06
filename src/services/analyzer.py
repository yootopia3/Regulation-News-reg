"""
2-Tier Hybrid Analyzer for MarketPulse-Reg

Tier 1 (Gatekeeper): Fast filtering with gemini-2.5-flash-lite
Tier 2 (Analyst): Deep analysis with gemini-3-flash-preview for important news only
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from src.config.settings import (
    MODEL_FILTER_ID,
    MODEL_ANALYZER_ID,
    MODEL_ANALYZER_FALLBACK,
    IMPORTANCE_THRESHOLD,
    API_CALL_DELAY,
    load_env,
    get_gemini_api_key,
)

logger = logging.getLogger(__name__)


class HybridAnalyzer:
    """2-Tier Hybrid Analyzer with Gatekeeper + Analyst pipeline."""

    def __init__(self):
        load_env()
        api_key = get_gemini_api_key()

        genai.configure(api_key=api_key)
        
        self.filter_model = MODEL_FILTER_ID
        self.analyzer_model = MODEL_ANALYZER_ID
        self.analyzer_fallback = MODEL_ANALYZER_FALLBACK
        self.importance_threshold = IMPORTANCE_THRESHOLD
        
    def _call_api(self, model_name: str, prompt: str, max_retries: int = 3) -> Optional[str]:
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

    def filter(self, title: str, description: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 1: Gatekeeper - Quick relevance filtering.
        Uses only title + description to save tokens.
        """
        prompt = f"""
        You are a news relevance filter for a Korean commercial bank's risk management team.
        
        **Task**: Determine if this news is relevant to "Korean commercial banks' risk management" and assign an importance score.
        
        **Input**:
        - Source: {agency_name}
        - Title: {title}
        - Summary: {description}
        
        **Scoring Guidelines (Based on 'Banking Business Impact' & 'Actionability')**:
        
        **High (Score 4-5): Immediate Strategy Revision / ALCO Agenda (Must Act)**
        *Criteria: If the news requires an ALCO or Risk Committee meeting tomorrow, or impacts the following:*
        1. **4 Pillars**:
           - **Loan (여신)**: DSR/LTV changes, Provisioning rules, Underwriting guidelines.
           - **Deposit (수신)**: Rate disclosure rules, liquidity coverage requirements, funding competition limits.
           - **Compliance (준법)**: Bank Act amendments, Internal Control (Book of Responsibilities), Consumer Protection Act.
           - **Capital (재무)**: BIS ratio rules, Dividend restrictions, LCR/NSFR changes.
        2. **Market/Biz Impact**:
           - **Macro**: BOK Base Rate decisions, Major liquidity supply.
           - **New Biz**: Permission for new ventures (Platform, non-financial), Restrictions on core earnings (Interest income).
           - **Spillover**: Major crises in securities/insurance sectors affecting bank subsidiaries or stability.
        
        **Moderate (Score 3): Monitoring / Watch List**
        *Criteria: General market monitoring or indirect references.*
        - **Market**: Exchange rate/Interest rate trends (without policy shifts).
        - **Indirect**: Regulations for other sectors (Card/Insurance) with minor spillover to banks.
        - **Reports**: Household debt stats (monthly), Delinquency rate trends (if not crisis level).

        **Low (Score 1-2): Routine / Irrelevant**
        *Criteria: Administrative or unrelated.*
        - **Routine**: Bond auctions, weekly schedules, holiday notices.
        - **Admin**: Personnel news, Awards, MOUs without binding policy changes.
        - **Irrelevant**: Exclusive issues of other sectors (Savings banks, Pawn shops) with zero bank impact.
        
        **Output** (JSON only):
        {{
            "is_relevant": boolean, (True if Score >= 1, False if completely unrelated like 'Ads')
            "importance_score": integer (1-5)
        }}
        """
        
        response_text = self._call_api(self.filter_model, prompt)
        
        if response_text:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse filter response: {response_text[:100]}")
                return None
        return None

    def analyze(self, title: str, full_content: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 2: Analyst - Deep analysis for important news.
        Uses full article content.
        """
        prompt = f"""
        # Role
        당신은 시중은행 전략기획부(CSO) 및 리스크관리부(CRO) 소속 수석 분석가입니다. 
        당신의 임무는 금융당국의 보도자료를 분석하여 '은행 실무 및 리스크'에 미치는 영향을 평가하고, 경영진이 즉시 의사결정할 수 있는 리포트를 작성하는 것입니다.

        # Core Philosophy (Action-Focused)
        "이 뉴스로 인해 은행이 내부 규정, 판매 절차, 자본 계획을 수정해야 하는가?"
        - 은행의 4대 요소[여신(대출), 수신(예금), 컴플라이언스(준법), 재무(자본)]에 직접적인 영향을 주면 무조건 [High]입니다.
        - 단순 인사, 동정, 타 업권(증권/보험 단독) 소식은 [Low]로 분류합니다.

        # Constraints
        - 스타일: 이모지 사용 절대 금지, 명사형 종결(~함, ~임) 사용.
        - 톤앤매너: 냉철하고 전문적인 리서치 리포트 스타일.
        - 리스크 분류: 반드시 [신용, 시장, 운용, 유동성, 금리, 기타] 중 해당되는 것을 모두 선택하십시오.

        # Output Format (Strict JSON)
        {{
            "published_date": "YYYY-MM-DD",
            "source": "{agency_name}",
            "importance": {{
                "score": 1-5,
                "level": "High/Medium/Low",
                "reason": "중요도 판단 근거 (은행 실무 관점) - 50자 이내"
            }},
            "classification": {{
                "pillars": ["여신", "수신", "컴플라이언스", "재무" 중 해당 항목 복수 선택 가능],
                "risk_tags": ["신용", "시장", "운용", "유동성", "금리", "기타" 중 해당 리스크 복수 선택 가능]
            }},
            "content": {{
                "title": "보도자료 핵심 제목 (30자 이내)",
                "key_points": ["핵심 내용 요약 1", "핵심 내용 요약 2", "핵심 내용 요약 3"],
                "impact_analysis": "은행 비즈니스 및 규제 환경에 미치는 심층 영향 분석 (최대 3문장)",
                "action_items": ["내일 오전까지 실행 또는 검토해야 할 구체적 조치 1", "내일 오전까지 실행 또는 검토해야 할 구체적 조치 2"]
            }}
        }}

        # Input Text
        Title: {title}
        Source: {agency_name}
        Content:
        {full_content[:3000]}
        """
        
        # Try primary model
        response_text = self._call_api(self.analyzer_model, prompt)
        
        # Fallback if primary fails
        if not response_text:
            logger.warning(f"Primary model {self.analyzer_model} failed. Trying fallback {self.analyzer_fallback}")
            response_text = self._call_api(self.analyzer_fallback, prompt)
        
        if response_text:
            try:
                # Remove Markdown code block if present
                clean_text = response_text.replace('```json', '').replace('```', '').strip()
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
                    "analyzed_by": self.analyzer_model # Keep track of which model was used
                }
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse analysis response: {e}, Text: {response_text[:100]}")
                return None
        return None

    def _is_personnel_announcement(self, title: str, agency_name: str) -> bool:
        """
        Check if the article is a personnel announcement from key agencies.
        Personnel announcements from any agency are HIGH importance.
        """
        # Key agencies - ALL agencies we track
        key_agencies = ['금융감독원', '금융위원회', '기획재정부', '한국은행', 'FSS', 'FSC', 'MOEF', 'BOK']
        
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

    def _apply_keyword_safeguards(self, title: str, current_score: int) -> int:
        """
        Apply rule-based safeguards to ensure important keywords are not undervalued by AI.
        Reads rules from config/safeguard_keywords.json.
        """
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'safeguard_keywords.json')
            if not os.path.exists(config_path):
                return current_score
                
            with open(config_path, 'r', encoding='utf-8') as f:
                safeguards = json.load(f)
            
            new_score = current_score
            
            # Check High Importance (Score 5)
            for keyword in safeguards.get('high_importance', {}).get('keywords', []):
                if keyword in title:
                    if new_score < 5:
                        logger.info(f"🛡️ Safeguard triggered (High): '{keyword}' found. Boosting score {current_score} -> 5")
                        return 5
            
            # Check Medium Importance (Score 4)
            for keyword in safeguards.get('medium_importance', {}).get('keywords', []):
                if keyword in title:
                    if new_score < 4:
                        logger.info(f"🛡️ Safeguard triggered (Medium): '{keyword}' found. Boosting score {current_score} -> 4")
                        new_score = 4
                        
            return new_score
            
        except Exception as e:
            logger.error(f"Error applying safeguards: {e}")
            return current_score

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
        importance_score = self._apply_keyword_safeguards(title, original_score)
        
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


# Backward compatibility alias
RegulationAnalyzer = HybridAnalyzer


if __name__ == "__main__":
    analyzer = HybridAnalyzer()
    logger.info("HybridAnalyzer initialized successfully.")
