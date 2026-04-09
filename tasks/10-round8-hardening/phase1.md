# Phase 1: deprecated-constants-removal

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C6, §7.3, §8.3 phase 1, §12 Q4)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/config/settings.py` — L31–61. 특히:
  - L36 `MODEL_FILTER_ID = os.environ.get(...)` (deprecated module-level constant)
  - L39 `MODEL_ANALYZER_ID = os.environ.get(...)` (deprecated)
  - L42 `MODEL_ANALYZER_FALLBACK = os.environ.get(...)` (deprecated)
  - L47–61 `get_model_filter_id()`, `get_model_analyzer_id()`, `get_model_analyzer_fallback()` getters (정상 경로)
- `/home/pacer/projects/reg_brief/scripts/admin/reanalyze_articles.py` — L13: `from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK` 가 유일한 deprecated 상수 consumer.
- `/home/pacer/projects/reg_brief/tests/unit/config/test_settings_env.py` — deprecated 상수의 import-time 동작을 검증하는 기존 테스트.
- `/home/pacer/projects/reg_brief/config/settings.py` — 루트 shim. `from src.config.settings import *` 한 줄. 자동으로 따라간다.
- `/home/pacer/projects/reg_brief/src/services/analyzer/hybrid.py` — getter 사용 패턴 참고 (`get_model_analyzer_id()` 호출 위치).

이전 phase의 작업물도 확인하라:

- 본 phase 가 task 10 의 첫 phase 다. 단, **task 8 phase 5** (`scripts/admin/_preserve.py` 신설 + `scripts/admin/reanalyze_articles.py` 의 preserve_pdf_url 적용) 가 이미 완료되어 있어야 한다 — task 10 은 task 8/9 후속이다.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: deprecated module-level 상수 (`MODEL_FILTER_ID`, `MODEL_ANALYZER_ID`, `MODEL_ANALYZER_FALLBACK`) 를 완전히 제거하고, 유일 consumer 인 `scripts/admin/reanalyze_articles.py` 를 getter 로 교체.

1. **사전 grep 검증**: `grep -rn "MODEL_FILTER_ID\|MODEL_ANALYZER_ID\|MODEL_ANALYZER_FALLBACK" src/ tests/ scripts/ web/ config/ docs/ spec/ 2>/dev/null` 로 모든 사용처를 나열. 예상 결과:
   - `src/config/settings.py` (정의)
   - `scripts/admin/reanalyze_articles.py` (consumer)
   - `tests/unit/config/test_settings_env.py` (검증)
   - `config/settings.py` (shim 한 줄, `import *`)
   - `spec/`, `docs/archive/**`, `tasks/**` 에 있는 **문서 멘션** 은 건드리지 않는다 (역사적 스냅샷).
   - 위 4 곳 외에 코드 사용처가 있으면 phase 1 을 즉시 `error` 로 마킹하고 `error_message` 에 추가 사용처를 기록하라 (사용자 결정 필요).

2. **`src/config/settings.py` 수정**:
   - 아래 라인들 (대략 L26–44) **삭제**:
     ```python
     # Tier 1: Gatekeeper (Fast, cheap filtering) -- DEPRECATED constant.
     MODEL_FILTER_ID = os.environ.get("GEMINI_FILTER_MODEL", _DEFAULT_FILTER_MODEL)

     # Tier 2: Analyst (Deep analysis for important news) -- DEPRECATED constant.
     MODEL_ANALYZER_ID = os.environ.get("GEMINI_ANALYZER_MODEL", _DEFAULT_ANALYZER_MODEL)

     # Fallback if Tier 2 model unavailable -- DEPRECATED constant.
     MODEL_ANALYZER_FALLBACK = os.environ.get(
         "GEMINI_ANALYZER_FALLBACK_MODEL", _DEFAULT_ANALYZER_FALLBACK_MODEL
     )
     ```
   - 위쪽의 "Runtime consumers MUST use the getters below..." 주석 블록도 정리 (deprecated 라는 표현 → 단순한 "use the getters below" 로 다듬되, 핵심 내용은 유지). **삭제 라인 외에는 손대지 마라**.
   - `_DEFAULT_FILTER_MODEL`, `_DEFAULT_ANALYZER_MODEL`, `_DEFAULT_ANALYZER_FALLBACK_MODEL` 상수는 **유지** (getter 가 사용 중).
   - `get_model_filter_id()`, `get_model_analyzer_id()`, `get_model_analyzer_fallback()` 함수는 **유지**.

3. **`scripts/admin/reanalyze_articles.py` 수정**:
   - L13 `from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK` →
     `from src.config.settings import get_model_analyzer_id, get_model_analyzer_fallback`
   - 본문 안에서 `MODEL_ANALYZER_ID` 참조 → `get_model_analyzer_id()` 호출 (값을 변수에 받아 두고 reuse 해도 무방).
   - `MODEL_ANALYZER_FALLBACK` 참조 → `get_model_analyzer_fallback()`.
   - 다른 로직 (preserve_pdf_url 호출 포함) 은 건드리지 마라. **task 8 phase 5 의 변경을 보존**.

4. **`tests/unit/config/test_settings_env.py` 수정**:
   - 기존 deprecated 상수 검증 케이스 (`assert MODEL_FILTER_ID == ...`) 를 **삭제** 또는 **getter 기반으로 다시 작성**:
     - 권장: 삭제 후, getter 가 env 를 정확히 읽는지 검증하는 case 만 남긴다.
     - 예:
       ```python
       def test_get_model_filter_id_default(monkeypatch):
           monkeypatch.delenv('GEMINI_FILTER_MODEL', raising=False)
           from src.config.settings import get_model_filter_id
           assert get_model_filter_id() == 'gemini-2.5-flash-lite'

       def test_get_model_filter_id_env_override(monkeypatch):
           monkeypatch.setenv('GEMINI_FILTER_MODEL', 'override-model')
           from src.config.settings import get_model_filter_id
           assert get_model_filter_id() == 'override-model'
       ```
   - subprocess + import 트릭은 더 이상 필요 없음 (getter 는 매 호출마다 env 를 읽으므로 module reload 가 불필요).
   - 기존 테스트 함수가 deprecated 상수에 직접 의존했다면 **그 함수를 삭제** 하고 위와 같은 getter 케이스로 교체.

5. **import smoke 확인**:
   - `python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"` 통과.
   - `python3 -c "from src.config.settings import get_model_analyzer_id; print(get_model_analyzer_id())"` 통과.
   - `python3 -c "import scripts.admin.reanalyze_articles"` 통과 (env 미설정 시 `pytest.importorskip` 패턴 — 단, 본 phase 는 import smoke 를 그냥 try/except 로 감싸서 무시해도 무방. AC 에서 명시).

## Acceptance Criteria

```bash
# 1) deprecated 상수가 src/config/settings.py 에서 사라졌는가
! grep -q '^MODEL_FILTER_ID = ' src/config/settings.py
! grep -q '^MODEL_ANALYZER_ID = ' src/config/settings.py
! grep -q '^MODEL_ANALYZER_FALLBACK = ' src/config/settings.py

# 2) getter 는 그대로 존재하는가
grep -q "^def get_model_filter_id" src/config/settings.py
grep -q "^def get_model_analyzer_id" src/config/settings.py
grep -q "^def get_model_analyzer_fallback" src/config/settings.py

# 3) reanalyze_articles.py 가 getter 를 import 하는가
grep -q "from src.config.settings import get_model_analyzer_id" scripts/admin/reanalyze_articles.py
! grep -q "MODEL_ANALYZER_ID" scripts/admin/reanalyze_articles.py
! grep -q "MODEL_ANALYZER_FALLBACK" scripts/admin/reanalyze_articles.py

# 4) src/ tests/ scripts/ 에 deprecated 상수의 잔재가 없는가
! grep -rn "^MODEL_FILTER_ID\|^MODEL_ANALYZER_ID\|^MODEL_ANALYZER_FALLBACK" src/ tests/unit/

# 5) 전체 단위 테스트 통과
python3 -m pytest tests/unit -q

# 6) import smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer; from src.config.settings import get_model_analyzer_id; print('OK', get_model_analyzer_id())"

# 7) reanalyze_articles import smoke (env 가 없을 수 있으므로 try)
python3 - <<'PY'
try:
    import scripts.admin.reanalyze_articles
    print("reanalyze_articles import OK")
except Exception as e:
    # env 부재로 인한 import 실패는 허용 (load_dotenv 시점)
    print(f"reanalyze_articles import skipped: {type(e).__name__}: {e}")
PY
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/10-round8-hardening/index.json`의 phase 1 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
사전 grep 단계에서 예상하지 못한 추가 consumer 가 발견되면 phase 1 을 즉시 `error` 로 마킹하고 `error_message` 에 그 사용처를 기록하라 — 임의로 추가 수정하지 마라.

## 주의사항

- **scripts/admin/reanalyze_articles.py 외 다른 scripts/admin/*.py 절대 건드리지 마라**. 이 phase 의 scope 는 deprecated 상수 제거에 한정된다.
- **task 8 phase 5 에서 추가된 `preserve_selected_keys` 호출 코드** 를 절대 지우지 마라. import 라인만 갈아끼우는 변경.
- `_DEFAULT_FILTER_MODEL` 등 underscore-prefixed 상수는 getter 가 default 로 사용하므로 유지.
- `MODEL_FILTER_ID` 라는 식별자가 spec/`tasks/`/`docs/archive/` 안 문서에 등장하는 것은 **역사적 스냅샷** — 건드리지 마라.
- 루트 `config/settings.py` 는 `from src.config.settings import *` shim 이므로, src 쪽에서 상수가 사라지면 자동으로 reflection 된다. 별도 수정 불필요.
- test_settings_env.py 의 subprocess 트릭 (이전에 module 을 fresh import 하기 위해 사용) 은 getter 패턴에서는 의미가 없으므로 정리 가능하면 정리.
- env 가 없는 환경에서 `import scripts.admin.reanalyze_articles` 가 실패할 수 있다 — 이 경우 phase 를 fail 처리하지 말고 import smoke 를 try/except 로 감싸서 통과시켜라 (AC 7 참조).
