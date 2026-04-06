# Phase 4: Analyzer Decompose

`src/services/analyzer.py` (361 LOC) 를 책임별로 분해한다. 프롬프트, 모델 호출,
키워드 safeguard, 결과 매핑이 한 클래스에 뭉쳐 있다.

## 사전 준비

설계 의도:

- `spec/refactor-round1.md` — 분석 결과 JSON 키 셋이 동일 유지되어야 함
- `spec/backend-architecture.md` — `src/services/analyzer/` 목표 구조

핵심 소스:

- `src/services/analyzer.py` 전체 (현재 361 LOC, `HybridAnalyzer` 클래스)
- `config/safeguard_keywords.json` — safeguard 룰 데이터
- `src/pipeline.py` — `self.analyzer.process(...)` 호출부

이전 phase 산출물:

- `spec/backend-architecture.md`
- `src/config/settings.py` (phase 2)
- `src/db/client.py` (phase 3, 이번 phase에서는 무관)

## 작업 내용

기존 단일 파일을 패키지로 전환:

```
src/services/analyzer/
  __init__.py          # HybridAnalyzer + RegulationAnalyzer 알리아스 노출
  prompts.py           # 프롬프트 빌더
  gemini_client.py     # Gemini SDK 래퍼 (call_api + retry)
  safeguards.py        # 키워드 safeguard 적용
  result_mapper.py     # API 응답 → 내부 dict 변환
  hybrid.py            # HybridAnalyzer 본체 (슬림 오케스트레이터)
```

### 4.1 `prompts.py`

- `def build_filter_prompt(title: str, description: str, agency_name: str) -> str`
  — 현재 `analyzer.py:92-133` 의 filter 프롬프트 문장을 **그대로** 옮겨라. 한
  글자도 바꾸지 마라.
- `def build_analyze_prompt(title: str, full_content: str, agency_name: str) -> str`
  — 현재 `analyzer.py:150-191` 의 analyze 프롬프트를 **그대로** 옮겨라. `[:3000]`
  슬라이스 포함.

### 4.2 `gemini_client.py`

- `class GeminiClient`:
  - `__init__(self, api_key: str)` — `genai.configure(api_key=api_key)` 호출.
  - `def call_json(self, model_name: str, prompt: str, max_retries: int = 3) -> str | None`
    — 현재 `_call_api` 로직을 그대로 옮긴다. 429/RESOURCE_EXHAUSTED 백오프, 404
    fast-fail, 일반 에러 5초 sleep — 모두 동일.
- 모듈 top-level에서 `genai.configure` 호출 금지.

### 4.3 `safeguards.py`

- `def load_safeguard_keywords(path: Path | None = None) -> dict` — phase 2에서
  만든 `SAFEGUARD_KEYWORDS_PATH` 사용. 파일 없으면 빈 dict.
- `def apply_keyword_safeguards(title: str, current_score: int, rules: dict) -> int`
  — 현재 `_apply_keyword_safeguards` 로직 그대로. 동일 로깅 메시지(`🛡️ Safeguard
  triggered ...`).
- `def is_personnel_announcement(title: str, agency_name: str) -> bool` — 현재
  `_is_personnel_announcement` 로직 그대로 (현재 호출되지 않더라도 보존).

### 4.4 `result_mapper.py`

- `def parse_filter_response(text: str) -> dict | None` — 현재 `filter()`의 JSON
  파싱 부분.
- `def parse_analyze_response(text: str, model_name: str) -> dict | None` —
  현재 `analyze()`의 markdown 제거 + JSON 파싱 + DB 스키마 변환(`summary`,
  `impact_analysis`, `action_items`, `risk_level`, `risk_score`, `risk_tags`,
  `pillars`, `analyzed_by`) 부분 그대로. 키 이름·구조 절대 변경 금지.

### 4.5 `hybrid.py`

- `class HybridAnalyzer`:
  - `__init__(self)`:
    - `from src.config.settings import get_gemini_api_key, MODEL_FILTER_ID, MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK, IMPORTANCE_THRESHOLD`
    - `self._client = GeminiClient(get_gemini_api_key())`
    - `self._safeguard_rules = load_safeguard_keywords()` (한 번만 로드)
    - 모델 ID / threshold 보관.
  - `def filter(self, title, description, agency_name) -> dict | None`:
    - prompt build → `_client.call_json` → `parse_filter_response`.
  - `def analyze(self, title, full_content, agency_name) -> dict | None`:
    - 현재와 동일하게 primary → fallback 모델 순서.
  - `def process(self, article, agency_name, category='press_release') -> dict`:
    - 현재 `process()` 로직과 1:1 동일. `time.sleep(API_CALL_DELAY)` 위치, score
      보정 후처리(`risk_score < importance_score` 케이스), `analysis_status` 값
      모두 동일.

### 4.6 `__init__.py`

- `from src.services.analyzer.hybrid import HybridAnalyzer`
- `RegulationAnalyzer = HybridAnalyzer` (backward compat alias 유지)
- `__all__ = ["HybridAnalyzer", "RegulationAnalyzer"]`

### 4.7 기존 `src/services/analyzer.py` 처리

- 파일 삭제. 패키지 디렉토리(`src/services/analyzer/`)와 동일 이름 충돌이 없도록
  확실히 한다.
- `from src.services.analyzer import HybridAnalyzer` import 경로는 패키지
  `__init__.py`로 만족된다.
- `pipeline.py` 의 import 그대로 동작 확인.

## Acceptance Criteria

```bash
# 새 패키지 구조
test -f src/services/analyzer/__init__.py
test -f src/services/analyzer/prompts.py
test -f src/services/analyzer/gemini_client.py
test -f src/services/analyzer/safeguards.py
test -f src/services/analyzer/result_mapper.py
test -f src/services/analyzer/hybrid.py

# 기존 단일 파일 제거됨
! test -f src/services/analyzer.py

# import 사이드 이펙트 0건
python -c "from src.services.analyzer import HybridAnalyzer, RegulationAnalyzer"

# 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline"
```

> 라인 수는 phase 7 `regression-report.md` 에 기록만 하며, phase 4의 hard AC가
> 아니다.

## AC 검증 방법

위 명령 모두 통과 시 phase 4 status를 `"completed"`로.

3회 실패 시 `"error"` + `error_message`.

## 주의사항

- **프롬프트 문장은 한 글자도 바꾸지 마라.** 줄바꿈/공백/이모지/괄호 다 그대로.
- **결과 dict 키 이름과 구조는 절대 변경 금지.** `pipeline.py` 와 DB가 의존한다.
- 로깅 메시지 문구도 가능한 한 동일하게 유지 (운영 모니터링 의존).
- `time.sleep(API_CALL_DELAY)` 호출 위치(필터 후, 분석 후) 변경 금지.
- `genai` import는 `gemini_client.py` 안에서만. 다른 모듈에서 `import google.generativeai` 하지 마라.
- 새로운 unit test 작성 금지 (이번 라운드 scope 외).
- DB 스키마, `agencies.json`, `web/` diff 0건.
