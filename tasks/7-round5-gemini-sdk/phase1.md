# Phase 1: google-generativeai → google-genai 의존성 교체 + 래퍼 마이그레이션

## 사전 준비

먼저 아래 문서를 읽어 phase 실행 규칙과 Round 5 의 변경 원칙을 파악하라:

- `CLAUDE.md` — phase 실행 규칙, runner 동작, 커밋 컨벤션
- `docs/ARCHITECTURE.md` — analyzer layer 의 전체 컨텍스트 (이 phase 에서 docs 는 수정하지 않는다)

그리고 아래 핵심 소스 파일을 직접 읽어 **현재 공개 계약**을 파악하라. 리팩토링은 source-first 다:

- `requirements.txt` — 현재 `google-generativeai>=0.7.0` 이 한 줄. 다른 의존성 라인 (`beautifulsoup4`, `requests`, `python-dotenv`, `supabase`, `pytz`, `feedparser`, `python-dateutil`) 은 이 phase 에서 손대지 않는다.
- `src/services/analyzer/gemini_client.py` — **이 phase 에서 재작성되는 파일.** 55 줄. 현재 구 SDK 기반 구현의 `GeminiClient` 클래스, `call_json` 의 시그니처, 재시도/에러 분기 규칙, `time.sleep` 호출 지점, 로거 메시지 문구를 모두 파악하라.
- `src/services/analyzer/hybrid.py` — **읽기만 하고 이 phase 에서 수정 금지.** `self._client.call_json(...)` 의 호출 사이트와, 반환값이 falsy 일 때 `analyzer_fallback` 모델로 재호출하는 fallback 분기 (line 65~71) 를 반드시 확인하라. 이 fallback 은 `call_json` 이 실패 시 `None` 을 리턴한다는 계약에 의존한다.
- `src/services/analyzer/__init__.py` — `HybridAnalyzer` 를 re-export 하는 파일. AC 의 import smoke 경로 (`from src.services.analyzer import HybridAnalyzer`) 가 여기를 경유한다는 것을 확인하라.
- `tests/conftest.py` — `GEMINI_API_KEY` 등을 env 에서 pop 하는 방어선 (line 17~18). 신 SDK 는 반드시 **명시적으로 `api_key` 를 주입** 받는 형태여야 이 방어선과 호환된다. implicit env auth 금지.
- `tests/unit/analyzer/test_result_mapper.py`, `tests/unit/analyzer/test_safeguards.py` — 기존 analyzer 테스트 2 개. **이 두 파일은 `gemini_client` 를 import 하지 않는다.** 즉 `pytest tests/unit/analyzer -q` 만으로는 신 SDK 의 import 건강성을 검증할 수 없다. 이 phase 의 AC 는 별도로 import smoke 명령을 포함한다.

이전 phase 산출물: 없음 (이 phase 가 Round 5 의 첫 phase).

참고 (선택): `tasks/5-round3-cleanup/phase4.md`, `tasks/6-round4-upgrades/phase1.md` — 과거의 mechanical 의존성/버전 교체 phase. 작업 스타일/AC 엄격도 레퍼런스로 참고 가능.

공식 migration 가이드 매핑 요약 (`https://ai.google.dev/gemini-api/docs/migrate`):

| 항목 | 구 SDK | 신 SDK |
|---|---|---|
| 패키지 | `google-generativeai` | `google-genai` |
| import | `import google.generativeai as genai` | `from google import genai` |
| 인증 | `genai.configure(api_key=...)` | `genai.Client(api_key=...)` |
| 모델 생성 | `genai.GenerativeModel(name)` | 인스턴스 없음. 호출 시점에 `model=name` |
| 호출 | `model.generate_content(prompt, generation_config=GenerationConfig(...))` | `client.models.generate_content(model=name, contents=prompt, config=types.GenerateContentConfig(...))` |
| 응답 텍스트 | `response.text` | `response.text` (동일) |

문서보다 코드가 우선이다. 매핑과 현재 wrapper 구현의 공개 계약이 어긋나면 **현재 구현의 공개 계약** (시그니처·반환 시맨틱·에러 분기 규칙) 을 기준으로 신 SDK 호출을 짜 맞춰라.

## 작업 내용

세 가지 편집을 한 phase 안에서 **다음 순서로** 수행하라. 이 순서는 의존관계상 유일한 정답이다. 순서를 바꾸면 중간 상태에서 import 체인이 깨진다.

**(1) `requirements.txt` 교체 → (2) `pip install -r requirements.txt` → (3) `src/services/analyzer/gemini_client.py` 재작성.**

순서를 지키지 않을 때의 실패 양상:
- (2) 를 (1) 전에 돌리면 구 `requirements.txt` 기준으로 resolver 가 돌아 사실상 no-op 이 되고 `google-genai` 가 들어오지 않는다.
- (3) 을 (2) 전에 돌리면 재작성된 모듈 상단 `from google import genai` 가 import 타임에 ImportError 로 폭발한다.

### 1. `requirements.txt` 교체

정확히 한 줄만 in-place 치환하라:

- Before: `google-generativeai>=0.7.0`
- After:  `google-genai>=1.0.0`

다른 모든 라인 (`beautifulsoup4>=4.12.3`, `requests>=2.31.0`, `python-dotenv>=1.0.1`, `supabase>=2.4.0`, `pytz>=2023.3`, `feedparser>=6.0.10`, `python-dateutil>=2.8.2`) 은 절대 수정하지 마라. 버전 하한, 공백, 줄 순서, 줄 끝 개행, 파일 끝 개행까지 전부 그대로 유지.

### 2. 신 SDK 설치 — `pip install -r requirements.txt`

이 phase 안에서 **정확히 1 회** 실행하라:

```bash
pip install -r requirements.txt
```

이 시점에는 단계 (1) 이 이미 끝나 있으므로 `requirements.txt` 의 `google-genai>=1.0.0` 이 resolver 대상이 되어 실제로 설치된다.

금지 사항:
- `pip uninstall -y google-generativeai` 를 실행하지 마라. `google` 은 Python namespace package 이고 `google.generativeai` 와 `google.genai` 는 서로 다른 서브패키지로 공존 가능하다. 이 phase 이후 runtime 에서는 누구도 `google.generativeai` 를 import 하지 않으므로 남아 있어도 dead weight 일 뿐 혼선이 없다. uninstall 은 dev 머신의 다른 툴체인이나 `scripts/archive/debug-round0/**` 의 과거 디버깅 스크립트를 깰 수 있는 불필요한 side effect 다.
- `pip install google-genai` 같은 개별 설치 명령을 쓰지 마라. 의존성 동기화는 반드시 `pip install -r requirements.txt` 한 형태로 통일한다.
- `requirements-dev.txt` 같은 보조 파일을 새로 만들지 마라. 이 레포에 그런 파일은 존재하지 않는다.

설치 실패 처리:
- 네트워크/resolver 문제로 실패하면 status 를 `"error"` 로, `"error_message"` 에 `pip install` 출력의 핵심 라인을 기록하고 중단하라.
- 오프라인 환경 / private PyPI 인증 / proxy 설정 같은 **사용자 수동 개입** 이 필요한 경우에는 `"blocked"` 로, `"blocked_reason"` 에 사유를 구체적으로 기록하고 즉시 중단하라.

### 3. `src/services/analyzer/gemini_client.py` 재작성

파일 전체를 재작성한다. 공개 계약은 **bit-for-bit 보존** 해야 한다.

#### 공개 계약 (변경 금지)

- 모듈에 `GeminiClient` 클래스 단 하나만 존재.
- 생성자 `GeminiClient.__init__(self, api_key: str)` — 외부에서 `api_key` 를 명시 주입받는다. env 에서 읽으면 안 된다 (`tests/conftest.py:17-18` 의 env pop 방어선과 충돌).
- 메서드 `GeminiClient.call_json(self, model_name: str, prompt: str, max_retries: int = 3) -> Optional[str]` — 시그니처, 기본값, 타입 힌트 그대로.
- **반환 시맨틱:**
  - 성공 & `response.text` 가 truthy → 해당 **raw JSON 문자열** 그대로 리턴 (파싱/trim/strip 금지).
  - `response.text` 가 `None` 또는 빈 문자열 → `None`.
  - 404/NOT_FOUND 예외 → 즉시 `None` 리턴, 재시도 없음.
  - 429/RESOURCE_EXHAUSTED 예외 → `base_delay * (attempt + 1)` 초 sleep 후 다음 시도.
  - 기타 예외 → `time.sleep(5)` 후 다음 시도.
  - `max_retries` 소진 → `None`.
- **`base_delay = 10`** 유지. `time.sleep(5)` 유지. 이 숫자는 회귀 방지용 고정값이다. 변경 금지.
- 로거: `logger = logging.getLogger(__name__)` 유지.
- 로그 메시지 문구도 가능한 한 그대로 유지 (관측성 회귀 방지):
  - Rate Limit: `f"Rate Limit hit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})"`
  - 404: `f"Model {model_name} not found"`
  - 기타: `f"API Error ({model_name}): {error_str[:200]}"`
  - 소진: `"Failed after max retries"`
- **모듈 상단 `import time` 그대로 유지. `from time import sleep` 으로 바꾸지 마라.** 이유: Phase 2 의 mock 경계가 `src.services.analyzer.gemini_client.time.sleep` 이다. import 형태를 바꾸면 mock target 이 어긋난다.

#### 신 SDK 호출 패턴 (시그니처 수준 예시)

```python
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
```

#### 세부 규칙

- `self._client = genai.Client(api_key=api_key)` 는 `__init__` 에서 **1 회만** 생성한다. 매 `call_json` 호출마다 Client 를 재생성하지 마라.
- `types.GenerateContentConfig(...)` 는 `call_json` 안에서 **한 번만** 생성해 재시도 루프 바깥 변수 (`config`) 로 보관하고, 루프 안 `generate_content` 호출에 재사용하라. 루프 안에서 매 시도마다 재생성하지 마라.
- `types.GenerateContentConfig(...)` 에는 **오직 `response_mime_type="application/json"`** 만 전달하라. 다른 필드 (`response_schema`, `temperature`, `max_output_tokens`, `top_p`, `top_k`, `system_instruction`, `safety_settings`, `stop_sequences`, `candidate_count` 등) 를 **추가하거나 제거하지 마라.** 현재 wrapper 의 공개 계약에 들어있지 않은 필드다.
- `genai.configure(...)` 는 구 SDK API 다. 신 SDK 에는 존재하지 않는다. **호출하지 마라.**
- `genai.GenerativeModel(...)` 역시 구 SDK API. **사용하지 마라.** 모델 이름은 `client.models.generate_content(model=..., ...)` 의 `model=` 키워드로 매 호출마다 전달한다.
- `response` 접근 방식은 **`getattr(response, "text", None)` 한 가지** 로 통일. `response.text` 직접 접근 + try/except 이중 방어 금지. 이유: 분기가 하나여야 Phase 2 의 테스트가 깔끔하고 mock 설계가 단순해진다.
- 재시도 에러 분기를 `google.genai.errors.APIError.code` 같은 타입 기반으로 리팩토링하지 마라. 이유: 이번 라운드 scope 는 "SDK 내부 교체" 에 한정된다. 에러 핸들링 전략 변경은 별도 후속 라운드로 분리해야 회귀 원인 판별이 가능하다.
- `time.sleep(...)` 호출 지점 (429 분기, 기타 예외 분기) 은 현재 코드와 동일 위치에 유지. Phase 2 의 mock 이 이 두 지점의 sleep 호출 횟수/인자를 검증한다.

#### 수정 금지 파일

- `src/services/analyzer/hybrid.py` — 단 한 바이트도 바꾸지 마라.
- `src/services/analyzer/__init__.py` — 단 한 바이트도 바꾸지 마라.
- `src/services/analyzer/prompts.py`, `result_mapper.py`, `safeguards.py` — 단 한 바이트도 바꾸지 마라.
- `src/config/settings.py` — 단 한 바이트도 바꾸지 마라.
- `scripts/archive/**` — 이 디렉토리의 어떤 파일도 건드리지 마라. legacy `google.generativeai` import 가 남아 있어도 그대로 둔다 (과거 디버깅 스냅샷, Round 5 scope 밖).
- `tests/**` — Phase 1 에서는 어떤 테스트 파일도 신설/수정하지 마라. 테스트 추가는 Phase 2 의 단독 산출물이다.
- `docs/**`, `spec/**`, `.github/**`, `web/**` — 건드리지 마라.

## Acceptance Criteria

```bash
# 1) 의존성 동기화 — 신 SDK 설치 + import 가능 여부 독립 검증
#    (각 줄은 독립된 명령. 순차 실행하되 bash && 체이닝 또는 set -e 환경에서 돌려라.)
pip install -r requirements.txt
python3 -c "from google import genai; print(genai)"

# 2) requirements.txt 교체 형상
grep -Fxq 'google-genai>=1.0.0'       requirements.txt
! grep -q  'google-generativeai'       requirements.txt

# 3) wrapper 모듈 import 체인 smoke — 신 SDK 가 모듈 로드 타임에 살아있어야 함
#    (기존 analyzer pytest 2 개 파일은 gemini_client 를 import 하지 않으므로
#     이 smoke 가 import 회귀의 유일한 방어선이다.)
python3 -c "from src.services.analyzer.gemini_client import GeminiClient; from src.services.analyzer import HybridAnalyzer; print('import-ok')"

# 4) wrapper 내부 핵심 심볼 검증 — 공개 계약 / mock 경계 보존
grep -q  '^from google import genai'                                src/services/analyzer/gemini_client.py
grep -q  '^from google.genai import types'                          src/services/analyzer/gemini_client.py
grep -q  '^import time'                                             src/services/analyzer/gemini_client.py
grep -q  'genai.Client(api_key=api_key)'                            src/services/analyzer/gemini_client.py
grep -q  'self._client.models.generate_content'                     src/services/analyzer/gemini_client.py
grep -q  'types.GenerateContentConfig'                              src/services/analyzer/gemini_client.py
grep -q  'response_mime_type="application/json"'                    src/services/analyzer/gemini_client.py
grep -q  'getattr(response, "text", None)'                          src/services/analyzer/gemini_client.py
grep -q  'def call_json(self, model_name: str, prompt: str, max_retries: int = 3) -> Optional\[str\]' src/services/analyzer/gemini_client.py
# 구 SDK 흔적 완전 제거
! grep -q 'google.generativeai'                                     src/services/analyzer/gemini_client.py
! grep -q 'genai.configure'                                         src/services/analyzer/gemini_client.py
! grep -q 'GenerativeModel'                                         src/services/analyzer/gemini_client.py
! grep -q 'from google.generativeai'                                src/services/analyzer/gemini_client.py

# 5) hybrid.py 는 단 한 바이트도 바뀌면 안 됨
test -z "$(git diff --name-only HEAD -- src/services/analyzer/hybrid.py)"

# 6) 기존 analyzer 테스트 green
python3 -m pytest tests/unit/analyzer -q

# 7) scope guard — 허용된 파일만 수정되어야 함
unexpected="$(git diff --name-only HEAD -- requirements.txt src docs spec tests web scripts tasks .github \
  | grep -v -x 'requirements.txt' \
  | grep -v -x 'src/services/analyzer/gemini_client.py' \
  | grep -v -x 'tasks/7-round5-gemini-sdk/index.json' \
  | grep -v -E '^tasks/7-round5-gemini-sdk/phase[0-9]+-output\.json$')"
test -z "$unexpected"
```

## AC 검증 방법

위 명령들을 **bash `&&` 체이닝 또는 `set -e` 환경에서 순차 실행** 하라. 어느 한 줄이라도 실패하면 전체 AC 실패로 판정하라.

**검증 명령을 파이프 (`| tail`, `| head`, `| grep` 등) 뒤로 넘기지 마라.** 이유: bash 파이프라인의 종료 코드는 기본적으로 마지막 명령의 종료 코드를 따르므로, 앞 명령이 실패해도 마지막 명령의 0 에 의해 exit status 가 삼켜진다 (false green). 검증은 각 명령을 standalone 으로 돌려라.

모든 명령이 0 으로 종료하면 `tasks/7-round5-gemini-sdk/index.json` 의 phase 1 status 를 `"completed"` 로 변경하라.

수정 3 회 이상 시도해도 실패하면 status 를 `"error"` 로 변경하고 `"error_message"` 에 **어떤 AC 명령** 이 **어떤 실제 출력/exit code** 로 실패했는지 구체적으로 기록하고 중단하라. 특히 pip install 실패 시 resolver 출력의 핵심 라인, import smoke 실패 시 Python ImportError 트레이스의 마지막 줄, scope guard 실패 시 `unexpected` 변수의 내용을 필수 기록 항목으로 남겨라.

작업 중 사용자 개입이 반드시 필요한 상황 — 오프라인 환경, private PyPI 인증 필요, proxy 설정 필요, 로컬 pytest 바이너리 부재 등 — 이 발생하면 status 를 `"blocked"` 로, `"blocked_reason"` 에 사유를 구체적으로 기록하고 즉시 중단하라.

## 주의사항

- **"(1) requirements.txt 교체 → (2) pip install -r requirements.txt → (3) gemini_client.py 재작성" 순서를 뒤섞지 마라.** 이유: (2) 를 (1) 전에 돌리면 구 requirements 기준으로 resolver 가 no-op 이 되어 신 SDK 가 들어오지 않는다. (3) 을 (2) 전에 돌리면 재작성된 모듈이 import 타임에 ImportError 로 폭발한다. 이 순서는 의존관계상 유일한 정답이다.
- **`pip uninstall -y google-generativeai` 를 실행하지 마라.** 이유: `google` 은 namespace package 이고 `google.generativeai` 와 `google.genai` 는 서로 다른 서브패키지로 공존 가능하다. uninstall 은 dev 머신의 다른 툴체인이나 `scripts/archive/debug-round0/**` 의 과거 디버깅 스크립트를 깰 수 있는 불필요한 side effect 다.
- **`pip install google-genai` 같은 개별 설치를 쓰지 마라.** 의존성 동기화는 `pip install -r requirements.txt` 한 형태로 통일한다. `requirements-dev.txt` 같은 보조 파일을 새로 만들지도 마라 — 이 레포에는 그런 파일이 없다.
- **`requirements.txt` 에서 다른 라인을 건드리지 마라.** `beautifulsoup4`, `requests`, `python-dotenv`, `supabase`, `pytz`, `feedparser`, `python-dateutil` 의 버전 하한·공백·정렬·줄 끝 개행 전부 그대로. 치환은 정확히 `google-generativeai>=0.7.0` → `google-genai>=1.0.0` 한 줄뿐이다.
- **`src/services/analyzer/hybrid.py` 를 수정하지 마라.** 이 phase 의 scope 는 wrapper 내부 교체에 한정된다. hybrid.py 는 `self._client.call_json(...)` 를 통해서만 통신하며, fallback 분기 (line 65~71) 가 `None` 리턴 시맨틱에 의존한다. wrapper 쪽에서 그 계약만 유지하면 hybrid.py 는 건드릴 필요가 없다.
- **`scripts/archive/debug-round0/**` 의 어떤 파일도 건드리지 마라.** `list_stable_models.py`, `check_flash_models.py`, `debug_gemini.py`, `list_all_models.py`, `verify_flash_2.py`, `backfill_log*.txt` 전부 legacy import 가 남아 있어도 그대로 둔다. 과거 디버깅 스냅샷이고 Round 5 scope 밖이다.
- **`types.GenerateContentConfig(...)` 에 `response_mime_type` 외 필드를 추가하지 마라.** `response_schema`, `temperature`, `max_output_tokens`, `top_p`, `top_k`, `system_instruction`, `safety_settings`, `stop_sequences`, `candidate_count` 전부 금지. 이유: 현재 wrapper 는 해당 필드를 사용하지 않으므로 추가는 의미론 변경 = 회귀.
- **`genai.configure(...)` 를 호출하지 마라.** 신 SDK 에 존재하지 않는 구 API 다. 신 SDK 는 `genai.Client(api_key=...)` 만 사용한다.
- **`genai.Client()` 를 인자 없이 호출하지 마라.** 신 SDK 는 인자 없이 호출하면 env var `GEMINI_API_KEY` 를 읽으려 한다. 그러나 `tests/conftest.py:17-18` 이 import 시점에 해당 env 를 pop 한다. 반드시 `genai.Client(api_key=api_key)` 로 명시 주입.
- **매 호출마다 Client 를 재생성하지 마라.** `__init__` 에서 1 회 생성하고 `self._client` 로 보관. 신 SDK 의 Client 는 HTTP 핸들러를 포함할 수 있고, 재생성은 회귀 비용일 뿐이다.
- **`import time` 을 `from time import sleep` 으로 바꾸지 마라.** Phase 2 의 mock 경계가 `src.services.analyzer.gemini_client.time.sleep` 이다. import 형태를 바꾸면 mock target 이 어긋나 Phase 2 의 실 대기 0 원칙이 무너진다.
- **에러 분기를 타입 기반으로 리팩토링하지 마라.** 현재 `"429"` / `"RESOURCE_EXHAUSTED"` / `"404"` / `"NOT_FOUND"` 문자열 매칭을 그대로 유지한다. `google.genai.errors.APIError.code` 같은 타입 기반 전환은 후속 라운드로 분리해야 회귀 원인 판별이 가능하다.
- **`response.text` 를 try/except 로 감싸지 마라. `getattr(response, "text", None)` 한 가지 방식만 사용하라.** 이유: 분기가 하나여야 Phase 2 의 테스트가 깔끔하고 mock 설계가 단순해진다.
- **pytest AC 통과만으로 phase 를 완료하지 마라.** 기존 analyzer 테스트 2 개 (`test_result_mapper.py`, `test_safeguards.py`) 는 `gemini_client` 를 import 하지 않는다. pytest 만 돌리면 신 SDK 누락을 놓친다. 반드시 AC 의 import smoke (`python3 -c "from src.services.analyzer.gemini_client import GeminiClient; from src.services.analyzer import HybridAnalyzer; print('import-ok')"`) 가 성공해야 이 phase 가 완료다.
- **`python -m compileall`, `ruff --fix`, `black`, `isort`, `yapf` 같은 포매터/린터 일괄 실행 금지.** 의도치 않은 파일을 건드려 scope guard 가 터진다. 편집은 손으로 (Edit tool) 필요한 곳만 최소한으로.
- **Phase 1 에서 `tests/unit/analyzer/test_gemini_client.py` 를 만들지 마라.** Phase 2 의 단독 산출물이다. 이 phase 에서 먼저 만들면 Phase 2 의 scope guard 가 어긋난다.
- **runner 의 build_command 는 `pip install` 을 자동 실행하지 않는다.** `_runner/run-phases.py:200-221` 의 `verify_build` 가 phase 단위로 build_command 를 돌리지만, build_command 자체에는 pip install 이 없다 (네트워크/flaky 방지 원칙). 이 phase 가 설치를 끝내 놓지 않으면 build verification 단계에서 import smoke 가 폭발한다.
- **기존 테스트를 깨뜨리지 마라.** `python3 -m pytest tests/unit/analyzer -q` 는 이 phase 완료 시점에 무조건 green 이어야 한다.
