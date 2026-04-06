"""Prompt builders for the 2-Tier Hybrid Analyzer."""


def build_filter_prompt(title: str, description: str, agency_name: str) -> str:
    return f"""
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


def build_analyze_prompt(title: str, full_content: str, agency_name: str) -> str:
    return f"""
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
