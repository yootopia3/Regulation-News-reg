# Phase 7: model-id-env

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (§2 "Gemini 2-tier" — `MODEL_FILTER_ID`, `MODEL_ANALYZER_ID`, `MODEL_ANALYZER_FALLBACK`의 역할)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. source-first다:

- `src/config/settings.py` (특히 line 22-31 모델 ID 상수)
- `src/services/analyzer/hybrid.py` (소비처)
- `src/services/analyzer/gemini_client.py` (소비처)
- `web/app/api/report/route.ts` (Phase 5 결과. 이미 `GEMINI_REPORT_MODEL` fallback을 읽고 있음)
- `.env.example`, `web/.env.local.example` (Phase 1/2 결과)

이전 phase 산출물:

- Phase 1: `.env.example`, `web/.env.local.example`
- Phase 5: `web/app/api/report/route.ts`가 `process.env.GEMINI_REPORT_MODEL ?? 'gemini-3-flash-preview'`를 사용 중
- Phase 6: `src/config/agency_loader.py`

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **Gemini 모델 ID를 env 기반으로 단일화**한다. backend는 `GEMINI_ANALYZER_MODEL` / `GEMINI_FILTER_MODEL` / `GEMINI_ANALYZER_FALLBACK_MODEL`을, frontend는 `GEMINI_REPORT_MODEL`을 사용한다. 기본값(fallback 리터럴)은 `src/config/settings.py`와 `web/app/api/report/route.ts`에만 각각 1회씩 존재한다.

### 1. `src/config/settings.py` 수정

```python
import os

# ... 기존 import 유지 ...

# --- Model Configuration for 2-Tier Hybrid Analysis ---

# Tier 1: Gatekeeper (Fast, cheap filtering)
MODEL_FILTER_ID = os.environ.get("GEMINI_FILTER_MODEL", "gemini-2.5-flash-lite")

# Tier 2: Analyst (Deep analysis for important news)
MODEL_ANALYZER_ID = os.environ.get("GEMINI_ANALYZER_MODEL", "gemini-3-flash-preview")

# Fallback if Tier 2 model unavailable
MODEL_ANALYZER_FALLBACK = os.environ.get(
    "GEMINI_ANALYZER_FALLBACK_MODEL", "gemini-1.5-pro"
)
```

**주의**:
- `os.environ.get`은 순수 함수. import 시점에 env를 한 번 읽어 상수 값을 고정. 이는 기존 구조(`load_env()` 명시 호출 규약)와 호환된다.
- fallback 문자열은 Round 1 시점 값과 **완전히 동일**.
- `MODEL_*` 상수 이름 변경 금지. 소비처가 import 중.
- `IMPORTANCE_THRESHOLD`, `API_CALL_DELAY`, scraper 설정, 로깅 설정 등 다른 상수는 건드리지 말 것.

### 2. `web/app/api/report/route.ts` 확인·정리

Phase 5에서 이미 `reportModel: process.env.GEMINI_REPORT_MODEL ?? 'gemini-3-flash-preview'`가 들어가 있다. 이 phase에서는 해당 fallback 리터럴이 **`getEnv()` 함수 내부 단 1곳에만 존재**하는지 확인한다. 다른 곳에 `'gemini-3-flash-preview'` 문자열이 남아 있으면 제거.

추가 수정은 필요 없다 (이미 env 기반).

### 3. `.env.example` 업데이트

기존 키 유지하고 아래 블록 추가:

```
# --- Gemini models (override defaults; optional) ---
GEMINI_FILTER_MODEL=gemini-2.5-flash-lite
GEMINI_ANALYZER_MODEL=gemini-3-flash-preview
GEMINI_ANALYZER_FALLBACK_MODEL=gemini-1.5-pro
```

### 4. `web/.env.local.example` 업데이트

기존 키 유지하고 추가:

```
# --- Gemini report model (override default; optional) ---
GEMINI_REPORT_MODEL=gemini-3-flash-preview
```

### 5. 테스트 추가

**`tests/unit/config/test_settings_env.py`** (신규):

- env 미설정 시 `MODEL_ANALYZER_ID`가 기본 fallback 값임을 검증.
- env 설정 시 해당 값이 반영됨을 검증. 단 `src.config.settings`가 이미 import된 상태라면 상수는 import 시점에 fix되므로, `importlib.reload(settings)` 또는 env set → 서브프로세스로 검증.
- 실용적 방법: `subprocess.run([sys.executable, "-c", "import os; os.environ['GEMINI_ANALYZER_MODEL']='test-model'; from src.config.settings import MODEL_ANALYZER_ID; assert MODEL_ANALYZER_ID == 'test-model'"])` 스타일.

이 테스트가 OS 불안정이면 `importlib.reload` 사용해도 된다.

### 6. Grep 검증

다음 grep 결과가 `settings.py` fallback 1곳 + `web/app/api/report/route.ts`의 `getEnv()` fallback 1곳, 그리고 example 파일·docs·tests를 제외하면 **0건**이어야 한다:

```bash
grep -rn '"gemini-3-flash-preview"' src/ web/app web/lib \
  | grep -v 'src/config/settings.py' \
  | grep -v 'web/app/api/report/route.ts'
# 결과 0 줄이어야 함
```

## Acceptance Criteria

```bash
# settings.py가 env 기반으로 변경되었는지
grep -q 'GEMINI_ANALYZER_MODEL' src/config/settings.py
grep -q 'GEMINI_FILTER_MODEL' src/config/settings.py
grep -q 'GEMINI_ANALYZER_FALLBACK_MODEL' src/config/settings.py
# 모델 ID 상수 이름 보존
grep -q '^MODEL_ANALYZER_ID = ' src/config/settings.py
grep -q '^MODEL_FILTER_ID = ' src/config/settings.py
grep -q '^MODEL_ANALYZER_FALLBACK = ' src/config/settings.py
# backend 리터럴은 settings.py fallback 1곳만
test "$(grep -rn '"gemini-3-flash-preview"' src/ | grep -v 'src/config/settings.py' | wc -l)" = "0"
# web 리터럴은 getEnv() fallback 1곳만
test "$(grep -rn '"gemini-3-flash-preview"' web/app web/lib | grep -v 'web/app/api/report/route.ts' | wc -l)" = "0"
# example 파일 업데이트 확인
grep -q 'GEMINI_ANALYZER_MODEL' .env.example
grep -q 'GEMINI_REPORT_MODEL' web/.env.local.example
# 환경 미설정 시 기본값 유지
python3 -c "
import os
for k in ('GEMINI_FILTER_MODEL','GEMINI_ANALYZER_MODEL','GEMINI_ANALYZER_FALLBACK_MODEL'):
    os.environ.pop(k, None)
import importlib, src.config.settings as s
importlib.reload(s)
assert s.MODEL_FILTER_ID == 'gemini-2.5-flash-lite'
assert s.MODEL_ANALYZER_ID == 'gemini-3-flash-preview'
assert s.MODEL_ANALYZER_FALLBACK == 'gemini-1.5-pro'
"
# pytest 전체 green
python -m pytest -q
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
# web 회귀 없음
cd web && npm test && npm run build
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 7 status를 `"completed"`로 변경.

`importlib.reload` 검증이 실패하면 settings 모듈의 상태가 다른 테스트에서 오염된 것일 수 있다 — pytest에서는 별도 서브프로세스 fixture 사용.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **모델 ID 상수 이름 변경 금지.** `MODEL_FILTER_ID`, `MODEL_ANALYZER_ID`, `MODEL_ANALYZER_FALLBACK`은 소비처가 import 중이다.
- **분석용과 리포트용을 하나의 env로 통합하지 마라.** `GEMINI_ANALYZER_MODEL`과 `GEMINI_REPORT_MODEL`은 의도적으로 분리되어 있다 (결정 #9).
- **fallback 문자열 값 변경 금지.** 동작 변경 없음.
- **`load_env()` 구조 변경 금지.** 기존 명시 호출 규약을 유지한다.
- **`src/services/analyzer/*.py` 수정 금지.** 소비처는 `MODEL_*` 상수 이름만 본다. 이름이 바뀌지 않으므로 수정할 필요 없다.
- **`web/app/api/report/route.ts`를 Phase 5 이상으로 수정하지 마라.** 이 phase는 `/api/report`의 로직을 건드리지 않는다.
- **example 파일에 실제 값 넣지 마라.** 기본값 문자열은 OK (이미 공개된 모델명).
- `docs/`, `.github/workflows/` 수정 금지.
- 기존 테스트를 깨지 마라.
