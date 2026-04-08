# Phase 2: GeminiClient wrapper 회귀 테스트 신설

## 사전 준비

먼저 아래 문서를 읽어 phase 실행 규칙과 이 phase 의 제약을 파악하라:

- `CLAUDE.md` — phase 실행 규칙, runner 동작, 커밋 컨벤션
- `prompts/task-create.md` — phase 파일 구조 규칙 (참고용)

그리고 아래 핵심 소스 파일을 직접 읽고 테스트 대상과 경계를 파악하라. source-first:

- `src/services/analyzer/gemini_client.py` — **Phase 1 에서 신 SDK 로 재작성된 상태의 파일.** 이 파일의 모든 분기 (성공, 429/RESOURCE_EXHAUSTED 재시도, 404/NOT_FOUND 즉시 None, 기타 예외 재시도, response.text 없음, max_retries 소진) 를 이 phase 에서 테스트로 고정한다. **이 파일 자체는 이 phase 에서 수정하지 않는다.** 읽기만.
- `src/services/analyzer/hybrid.py` — **읽기만 하고 수정 금지.** `self._client.call_json(...)` 호출 사이트와 fallback 분기 (line 65~71) 가 `None` 반환에 어떻게 의존하는지 확인하라. 이 phase 의 테스트 케이스 7 이 이 계약을 직접 고정한다.
- `src/services/analyzer/__init__.py` — `HybridAnalyzer` re-export. 참고용.
- `tests/conftest.py` — `GEMINI_API_KEY` 등을 env 에서 pop 하는 방어선 (line 17~18). 새 테스트도 env 에 의존하지 않도록 설계하라.
- `tests/unit/analyzer/test_result_mapper.py`, `tests/unit/analyzer/test_safeguards.py` — 기존 analyzer 테스트 2 개. pytest 스타일, import 패턴, fixture 사용 여부 참고. `monkeypatch` 기반, 네트워크/파일시스템 의존 0 의 스타일을 유지하라.
- `requirements.txt` — **이 phase 에서 수정 금지.** Phase 1 에서 `google-genai>=1.0.0` 로 확정됨. `pytest-mock`, `responses`, `vcrpy`, `respx` 같은 신규 테스트 라이브러리를 추가하지 마라 — 이 레포의 테스트는 pytest 기본 `monkeypatch` 로만 돌아간다.

이전 phase (Phase 1) 산출물:
- `requirements.txt`: `google-generativeai>=0.7.0` → `google-genai>=1.0.0` 교체 완료.
- `src/services/analyzer/gemini_client.py`: 신 SDK 로 재작성 완료. 모듈 상단에 `import time`, `from google import genai`, `from google.genai import types` 세 import. `GeminiClient.__init__` 은 `self._client = genai.Client(api_key=api_key)` 한 줄. `call_json` 은 `self._client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(response_mime_type="application/json"))` 호출 + `getattr(response, "text", None)` 반환 + 429/404/기타 에러 분기 유지.

문서보다 코드가 우선이다. Phase 1 산출물과 이 phase 파일의 기술 매핑이 어긋나면 Phase 1 의 실제 소스를 기준으로 삼아라.

## 작업 내용

**신규 파일 1 개만** 생성한다: `tests/unit/analyzer/test_gemini_client.py`.

다른 어떤 파일도 수정/생성하지 마라. `src/**`, `hybrid.py`, `requirements.txt`, `scripts/archive/**`, `docs/**`, `spec/**`, `.github/**`, `web/**`, 기존 테스트 파일 2 개 전부 불변.

### 테스트 설계 원칙

1. **mock 경계는 wrapper 의 모듈 네임스페이스** 로 둔다. `google.genai` 패키지 자체를 patch 하지 말고, `src.services.analyzer.gemini_client` 내부에서 참조되는 심볼을 교체하라. 이래야 실제 `google.genai` 가 설치돼 있든 말든 테스트가 성립하고, 네트워크에 닿지 않는다:
   - `monkeypatch.setattr("src.services.analyzer.gemini_client.genai", <FakeGenai>)`
   - `monkeypatch.setattr("src.services.analyzer.gemini_client.types", <FakeTypes>)`
   - `monkeypatch.setattr("src.services.analyzer.gemini_client.time.sleep", lambda *_a, **_kw: None)`

2. **실 대기 0 초.** 모든 `time.sleep` 호출을 no-op 으로 치환하라. 이유: `call_json` 의 재시도 분기가 최대 30 초 sleep (`base_delay * attempt`) 와 5 초 sleep (기타 예외) 을 포함한다. 실제로 돌면 테스트 suite runtime 이 수십 초로 폭주한다.

3. **실 네트워크 0 회.** 테스트 파일에서 `from google import genai`, `import google.generativeai`, `requests`, `urllib`, `httpx`, `aiohttp`, `socket` 같은 네트워크 가능 라이브러리를 import 하지 마라. mock 된 가짜 객체만 사용.

4. **env 의존 0.** `GEMINI_API_KEY` 같은 환경변수에 의존하지 마라. `GeminiClient("fake-api-key")` 로 상수 주입.

5. **test isolation.** `monkeypatch` fixture 를 사용해 각 테스트 함수가 끝나면 자동 복원되게 하라. 전역 상태를 바꾸지 마라.

6. **FakeGenai / FakeTypes 헬퍼** 는 테스트 파일 내부에 직접 정의하라. 별도 fixture 파일/유틸 파일을 만들지 마라 — 이번 phase 는 단일 신규 파일만 허용한다.
   - `FakeGenai.Client(api_key=...)` 는 호출 가능 객체여야 하며, 반환값은 `models.generate_content(...)` 를 가진 가짜 클라이언트.
   - `FakeTypes.GenerateContentConfig(**kwargs)` 는 호출 시 kwargs 를 속성으로 가진 가짜 config 객체를 리턴. 테스트 케이스 6 이 이 속성을 검증한다.
   - 가짜 클라이언트의 `models.generate_content(**kwargs)` 는 테스트별로 동작을 바꿀 수 있어야 한다 (성공 시 fake response 리턴, 실패 시 특정 Exception raise). 호출 카운트와 호출 kwargs 는 캡처해서 assert 가능해야 한다.

7. **FakeResponse** 는 `text` 속성만 있는 단순 객체. `text = "<json str>"` 또는 `text = None` 또는 `text = ""` 중 하나. `getattr(response, "text", None)` 가 올바르게 동작해야 한다.

### 테스트 케이스 7 개 (반드시 모두 포함)

케이스마다 **별도 테스트 함수** 로 분리하라. `@pytest.mark.parametrize` 로 묶지 마라 — 실패 시 원인 판별이 흐려진다.

**케이스 1: 성공 경로**
- Fake `generate_content` 가 `FakeResponse(text='{"ok": 1}')` 를 리턴.
- `GeminiClient("fake-key").call_json("gemini-test-model", "prompt text")` 의 결과가 정확히 문자열 `'{"ok": 1}'` 와 동일한지 assert.
- `generate_content` 호출 횟수 = 1.
- mocked `time.sleep` 호출 횟수 = 0.

**케이스 2: 429 / RESOURCE_EXHAUSTED 재시도 후 성공**
- Fake `generate_content` 의 첫 호출은 `Exception("429 RESOURCE_EXHAUSTED: quota")` 를 raise, 두 번째 호출은 성공 response 리턴.
- `call_json(...)` 의 결과가 성공 응답 텍스트와 동일한지 assert.
- `generate_content` 호출 횟수 = 2.
- mocked `time.sleep` 호출 횟수 = 1, 호출 인자 = `10` (= `base_delay * (attempt + 1) = 10 * 1`, attempt 인덱스 0 기준).

**케이스 3: 404 / NOT_FOUND 즉시 None**
- Fake `generate_content` 가 `Exception("404 NOT_FOUND: model xyz")` 를 raise.
- `call_json(...)` 의 결과가 `None` 인지 `assert result is None` 으로 assert.
- `generate_content` 호출 횟수 = 1 (재시도 없음).
- mocked `time.sleep` 호출 횟수 = 0.

**케이스 4: 기타 예외 → max_retries 소진 후 None**
- Fake `generate_content` 가 매 호출마다 `Exception("500 INTERNAL ERROR")` 를 raise.
- `GeminiClient("fake-key").call_json("model", "prompt", max_retries=3)` 의 결과가 `None` 인지 `assert result is None`.
- `generate_content` 호출 횟수 = 3.
- mocked `time.sleep` 호출 횟수 = 3, 모든 호출 인자 = `5`.

**케이스 5: response.text 없음/빈값 → None**
- 서브케이스 A: Fake response 의 `text = None` → `call_json` 이 `None` 리턴, `generate_content` 호출 횟수 = 1, 재시도 없음.
- 서브케이스 B: Fake response 의 `text = ""` → 동일.
- 두 서브케이스를 같은 테스트 함수 안에서 둘 다 커버해도 되고, 별도로 쪼개도 된다. 단, 두 경우 모두 `result is None` 을 assert.

**케이스 6: GenerateContentConfig 인자 전달 검증**
- 성공 경로에서 `generate_content` 호출 시 전달된 kwargs 를 캡처.
- `kwargs["model"] == "gemini-test-model"` 를 assert (케이스에서 사용한 model_name 과 일치).
- `kwargs["contents"] == "prompt text"` 를 assert (케이스에서 사용한 prompt 와 일치).
- `kwargs["config"].response_mime_type == "application/json"` 을 assert.
- 추가로 `FakeTypes.GenerateContentConfig` 가 정확히 `response_mime_type="application/json"` 한 kwarg 로 호출되었는지 호출 캡처로 assert.

**케이스 7: hybrid 계약 — 실패 시 반드시 `None`**
- `hybrid.py:68` 의 `if not response_text:` 분기가 제대로 동작할 것을 보장하는 identity 테스트.
- `call_json` 이 실패 경로에서 `False`, `0`, `""` 같은 다른 falsy 값이 아니라 **정확히 `None` 객체** 를 리턴하는지를 `assert result is None` (그리고 `assert result is not False`, `assert result != 0`) 같은 엄격한 identity 검사로 고정하라.
- 대표 실패 케이스 (예: 404 분기 또는 max_retries 소진) 를 입력으로 사용해서 고정.
- 이 테스트는 `hybrid.HybridAnalyzer` 를 인스턴스화하지 않는다 — `GeminiClient.call_json` 의 반환값 identity 만 고정하는 방식으로 hybrid 계약을 간접 보장한다.

### 네트워크/sleep 가드

pytest `monkeypatch` fixture 에서 다음 3 개를 반드시 설정하라. 가능하면 모든 테스트 함수에 공통 적용되는 helper (예: 각 테스트 초반에 호출하는 작은 함수) 로 묶어 중복을 피하라:

```python
def _install_fakes(monkeypatch, fake_genai, fake_types):
    monkeypatch.setattr("src.services.analyzer.gemini_client.genai", fake_genai)
    monkeypatch.setattr("src.services.analyzer.gemini_client.types", fake_types)
    monkeypatch.setattr("src.services.analyzer.gemini_client.time.sleep", lambda *_a, **_kw: None)
```

패치 순서: **FakeGenai / FakeTypes / time.sleep 설정 → 그 다음 `GeminiClient("fake-key")` 인스턴스화.** 역순이면 `__init__` 에서 실제 `genai.Client` 를 호출하려다 SDK 동작에 따라 env 를 찾거나 네트워크에 닿을 수 있다.

### 금지 사항

- `from google import genai`, `import google.generativeai`, `from google.genai import types` **테스트 파일에서 import 하지 마라.** mock 된 fake 만 사용.
- `import time` 도 **하지 마라.** `time.sleep(...)` 을 테스트 파일에서 직접 호출하지 마라.
- `requests`, `urllib`, `httpx`, `aiohttp`, `socket` 등 네트워크 라이브러리 import 금지.
- `pytest-mock`, `responses`, `vcrpy`, `respx`, `freezegun` 같은 외부 의존성 금지. `monkeypatch` 는 pytest 기본이라 추가 설치 불필요.
- `hybrid.HybridAnalyzer` 를 실제로 인스턴스화하지 마라. `HybridAnalyzer()` 는 `get_gemini_api_key()` 를 호출해 settings 를 읽는데, `tests/conftest.py` 가 env 를 pop 한 상태라 실패한다. 이 phase 의 대상은 `GeminiClient` 뿐이다. 케이스 7 의 hybrid 계약은 "None identity 고정" 으로만 표현한다.
- 테스트 케이스 7 개를 `@pytest.mark.parametrize` 로 한 함수에 묶지 마라. 각 분기를 단독 함수로 유지하라.
- `gemini_client.py`, `hybrid.py`, `requirements.txt`, 기존 테스트 파일 2 개를 수정하지 마라.

## Acceptance Criteria

```bash
# 1) 신규 테스트 파일 존재
test -f tests/unit/analyzer/test_gemini_client.py

# 2) 정적 검사 — 실 SDK / 실 sleep / 실 네트워크 import 금지
! grep -q '^from google import genai'                       tests/unit/analyzer/test_gemini_client.py
! grep -q '^from google.generativeai'                       tests/unit/analyzer/test_gemini_client.py
! grep -q '^import google.generativeai'                     tests/unit/analyzer/test_gemini_client.py
! grep -q '^from google.genai import types'                 tests/unit/analyzer/test_gemini_client.py
! grep -q '^import time'                                    tests/unit/analyzer/test_gemini_client.py
! grep -q 'time.sleep('                                     tests/unit/analyzer/test_gemini_client.py
! grep -qE '^(import|from) (requests|urllib|httpx|aiohttp|socket)' tests/unit/analyzer/test_gemini_client.py

# 3) mock 경계 문자열이 테스트 파일에 정확히 존재
grep -q 'src.services.analyzer.gemini_client.genai'        tests/unit/analyzer/test_gemini_client.py
grep -q 'src.services.analyzer.gemini_client.types'        tests/unit/analyzer/test_gemini_client.py
grep -q 'src.services.analyzer.gemini_client.time.sleep'   tests/unit/analyzer/test_gemini_client.py

# 4) 테스트 대상 import
grep -q 'from src.services.analyzer.gemini_client import GeminiClient' tests/unit/analyzer/test_gemini_client.py

# 5) Phase 1 산출물 무변경 — 한 바이트도 바뀌면 안 됨
test -z "$(git diff --name-only HEAD -- src/services/analyzer/gemini_client.py)"
test -z "$(git diff --name-only HEAD -- src/services/analyzer/hybrid.py)"
test -z "$(git diff --name-only HEAD -- requirements.txt)"

# 6) analyzer 테스트 suite 전부 green (기존 2 개 + 신규 7 케이스)
python3 -m pytest tests/unit/analyzer -q

# 7) scope guard — 허용된 파일만 수정되어야 함
unexpected="$(git diff --name-only HEAD -- requirements.txt src docs spec tests web scripts tasks .github \
  | grep -v -x 'tests/unit/analyzer/test_gemini_client.py' \
  | grep -v -x 'tasks/7-round5-gemini-sdk/index.json' \
  | grep -v -E '^tasks/7-round5-gemini-sdk/phase[0-9]+-output\.json$')"
test -z "$unexpected"
```

## AC 검증 방법

위 명령들을 **bash `&&` 체이닝 또는 `set -e` 환경에서 순차 실행** 하라. 어느 한 줄이라도 실패하면 전체 AC 실패로 판정하라.

**검증 명령을 파이프 (`| tail`, `| head`, `| grep` 등) 뒤로 넘기지 마라.** 이유: bash 파이프라인의 종료 코드는 기본적으로 마지막 명령의 종료 코드를 따르므로 실패한 앞 명령의 exit status 가 삼켜진다 (false green). 특히 `/usr/bin/time ... python3 -m pytest ... | tail -5` 같은 패턴을 **절대 쓰지 마라** — pytest 가 실패해도 `tail` 이 0 으로 종료해 AC 가 green 처럼 보인다.

(6) 의 pytest 출력 요약에서 **`test_gemini_client.py` 의 7 개 테스트 케이스가 수집/실행/통과** 했는지 눈으로 확인하라.

모든 명령이 0 으로 종료하면 `tasks/7-round5-gemini-sdk/index.json` 의 phase 2 status 를 `"completed"` 로 변경하라.

수정 3 회 이상 시도해도 실패하면 status 를 `"error"`, `"error_message"` 에 어떤 AC 가 어떤 실제 출력으로 실패했는지 (특히 pytest 실패 시 실패 테스트 이름 + assertion 메시지, 정적 검사 실패 시 grep match, scope guard 실패 시 `unexpected` 내용) 구체적으로 기록하고 중단하라.

로컬에 `pytest` 가 설치되어 있지 않거나, 기타 사용자 수동 개입이 필요한 상황이 발생하면 `"blocked"` + `"blocked_reason"` 으로 기록하고 즉시 중단하라.

## 주의사항

- **테스트 runtime 을 AC 로 측정하려 하지 마라.** 이유: `/usr/bin/time ... python3 -m pytest ... | tail -N` 같은 파이프라인 기반 runtime 측정은 bash 기본 의미론에서 마지막 명령 (`tail`) 의 exit status 만 보므로 pytest 실패를 삼킨다 (false green). "실 대기 0 초" 보장은 AC (2) 의 정적 검사 (`^import time`, `time.sleep(` 금지) 와 AC (3) 의 mock 경계 검증 (`src.services.analyzer.gemini_client.time.sleep`) 로 이미 구조적으로 충분히 보장된다.
- **`| tail`, `| head`, `| grep` 같은 파이프라인을 AC 의 종료 코드 판정 경로에 사용하지 마라.** 이유: bash 는 기본적으로 파이프라인의 종료 코드를 마지막 명령의 것으로 취한다. `set -o pipefail` 이 없는 환경에서는 앞 명령의 실패가 모두 삼켜진다 (false green). AC 명령은 각각 standalone 으로 돌려라.
- **`src/services/analyzer/gemini_client.py` 를 한 바이트도 수정하지 마라.** Phase 1 에서 확정된 wrapper 를 건드리면 회귀 방어 계약이 흐트러진다. AC (5) 의 `git diff` 가드가 이를 구조적으로 막는다.
- **`src/services/analyzer/hybrid.py` 를 한 바이트도 수정하지 마라.** 같은 이유.
- **`requirements.txt` 를 수정하지 마라.** Phase 1 에서 이미 확정됨. `pytest-mock` 등 새 테스트 라이브러리를 추가하고 싶어지더라도 금지 — `monkeypatch` 는 pytest 기본이다.
- **실제 `google.genai` 를 테스트 파일에서 import 하지 마라.** `from google import genai`, `import google.generativeai`, `from google.genai import types` 전부 금지. 테스트는 SDK 의 존재 여부와 독립적이어야 한다.
- **`time.sleep` 을 직접 호출하지 마라. `import time` 도 하지 마라.** 이유: mock 경계 밖의 sleep 은 실제로 돌아 테스트 runtime 을 늘린다. 모든 sleep 은 `src.services.analyzer.gemini_client.time.sleep` mock 으로 처리.
- **네트워크를 호출할 수 있는 어떤 import 도 하지 마라.** `requests`, `urllib`, `httpx`, `aiohttp`, `socket` 직접 사용 금지.
- **테스트가 환경변수 `GEMINI_API_KEY` 에 의존하지 않도록 하라.** `tests/conftest.py:17-18` 이 이를 pop 한다. `GeminiClient("fake-api-key")` 처럼 문자열 상수 주입.
- **`hybrid.HybridAnalyzer` 를 실제로 인스턴스화하지 마라.** `HybridAnalyzer()` 는 settings 를 읽고 실제 API key 를 요구한다 (env pop 상태에서 실패). 케이스 7 은 순전히 `GeminiClient.call_json` 의 `None` identity 를 고정하는 방식으로 hybrid 계약을 간접 보장한다.
- **`pytest-mock`, `responses`, `vcrpy`, `respx`, `freezegun` 같은 새 의존성을 추가하지 마라.** `monkeypatch` 만 사용.
- **mock 경계를 `google.genai` 로 두지 마라. 반드시 `src.services.analyzer.gemini_client.genai` / `.types` / `.time.sleep` 로 두어라.** 이유: 후자는 wrapper 의 모듈 네임스페이스에서 resolve 되는 심볼을 교체하므로, 실제 `google.genai` 가 설치돼 있든 없든 테스트가 성립한다.
- **테스트 케이스 7 개를 합치거나 쪼개지 마라.** 각 케이스는 wrapper 의 한 분기를 단독으로 고정한다. 파라미터라이즈로 묶으면 실패 원인 판별이 어렵고, 케이스를 쪼개면 scope 를 초과한다.
- **`types.GenerateContentConfig` 의 인자 검증을 생략하지 마라.** `response_mime_type="application/json"` 이 빠지면 hybrid 파이프라인이 JSON 이 아닌 응답을 받아 `parse_filter_response` 가 깨진다. 이 값이 정확히 전달되는지 캡처해서 assert.
- **scope guard 의 `grep -v -x` 패턴을 느슨하게 만들지 마라.** 허용 목록은 정확히 3 항목 (신규 테스트 파일 + task index.json + phase output) 뿐이다. 이를 확장하면 우발 수정이 새어 들어올 수 있다.
- **기존 테스트를 깨뜨리지 마라.** `test_result_mapper.py`, `test_safeguards.py` 는 이 phase 에서 건드리지 말고, 통과 상태를 유지해야 한다.
