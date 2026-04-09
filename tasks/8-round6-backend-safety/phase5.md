# Phase 5: pdf-url-preserve-in-reanalyze

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C2, §4 OOS — `scripts/admin` 예외 조항, §11 R2, §11 R6 (backfill known limitation), §12 Q2)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/scripts/admin/reanalyze_articles.py` — **전체 읽기**. 특히:
  - L11: `from src.db.client import supabase` (lazy supabase 사용)
  - L13: `from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK` (이건 task 10 phase 1 에서 getter 로 교체할 예정. 본 phase 는 건드리지 않는다.)
  - L35: `supabase.table('articles').select('id, title, content, agency').execute()` — **`analysis_result` 컬럼이 SELECT 되지 않는다**. 본 phase 에서 SELECT 컬럼에 `analysis_result` 를 추가해야 preserve 가 가능하다.
  - L48–66: 재분석 루프. L61–65 가 `analysis_result` 를 직접 overwrite 하는 update 호출.
- `/home/pacer/projects/reg_brief/src/pipeline.py` `_save_item` (phase 4 에서 업데이트된 `pdf_url` merge 로직. 같은 의미론을 phase 5 의 helper 가 따라야 한다.)
- `/home/pacer/projects/reg_brief/src/utils/logger.py` (`src/utils/` 의 기존 위치 — preserve helper 도 같은 디렉토리에 둔다)

이전 phase의 작업물도 확인하라:

- Phase 4 의 `_save_item` 변경 (`tests/unit/pipeline/test_pdf_url_persist.py` 포함). preserve 함수의 시맨틱이 `_save_item` 의 merge 시맨틱과 정합해야 한다.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: 재분석 (`scripts/admin/reanalyze_articles.py`) 이 `analysis_result` 전체를 덮어쓸 때, 기존에 저장돼 있던 `pdf_url` 키가 유실되지 않도록 preserve 한다. **scope 는 reanalyze 1 파일 + helper 1 파일 + helper test 1 파일로 한정**.

> **Backfill 은 OOS**: `scripts/admin/run_backfill_safe.py` 도 line 269–272 에서 `analysis_result` 를 overwrite 하지만, 본 phase 에서는 손대지 않는다. 사유는 roadmap §11 R6 에 명시되어 있다 (preserve 적용에 추가 SELECT + 분석 루프 구조 변경이 필요해 최소 수정 원칙 위반). 별도 후속 micro-task 후보로 남긴다.

1. **preserve helper 신설**: `src/utils/preserve.py` (신규 파일)
   - 위치 결정 사유: 이미 `src/utils/logger.py` 가 존재하는 재사용 가능한 utility 디렉토리. round 1 의 의존성 방향 표 (`utils` 는 최하위, 다른 레이어 import 금지) 와 정합하며 (helper 는 순수 함수, 외부 의존성 0), `scripts/` 패키지화 같은 부수 효과 없이 양쪽 admin script 가 `sys.path.append(project_root)` 로 import 가능.
   - 내용:
     ```python
     """Helpers for preserving selected analysis_result keys across overwrites.

     Used by admin scripts (re-analysis, backfill) that need to update an
     article's analysis_result without losing fields that were inserted by
     other producers (e.g. pdf_url from sanction_scraper -> _save_item).
     """
     from typing import Dict, Optional, Tuple

     PRESERVED_KEYS: Tuple[str, ...] = ("pdf_url",)


     def preserve_selected_keys(
         old: Optional[Dict],
         new: Optional[Dict],
     ) -> Optional[Dict]:
         """Return ``new`` with ``PRESERVED_KEYS`` carried over from ``old``.

         Behavior:
         - If ``old`` is not a dict, ``new`` is returned unchanged.
         - If ``old`` has none of the preserved keys (or empty values), ``new``
           is returned unchanged.
         - If ``new`` is not a dict, a fresh dict is built containing only the
           carried-over keys.
         - If ``new`` already defines a preserved key, the existing value in
           ``new`` wins (we use ``setdefault``-style merge — "latest analysis
           wins for analysis fields, but never silently drops the carry").

         Pure function, no I/O, no logging.
         """
         if not isinstance(old, dict):
             return new
         carry = {k: old[k] for k in PRESERVED_KEYS if old.get(k)}
         if not carry:
             return new
         if not isinstance(new, dict):
             return dict(carry)
         merged = dict(new)
         for k, v in carry.items():
             merged.setdefault(k, v)
         return merged
     ```
   - import 시 사이드 이펙트 0. 어떤 외부 패키지도 import 하지 않는다 (`typing` 만).

2. **`scripts/admin/reanalyze_articles.py` 수정**:
   - L13 의 `from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK` 라인은 **건드리지 마라** (task 10 phase 1 에서 getter 로 교체할 예정). 본 phase 는 deprecated 상수와 무관.
   - L35 의 SELECT 컬럼에 `analysis_result` 를 추가:
     - 변경 전: `supabase.table('articles').select('id, title, content, agency').execute()`
     - 변경 후: `supabase.table('articles').select('id, title, content, agency, analysis_result').execute()`
   - 재분석 루프 안 (L48 부근) 에서 새 analyzer 결과를 받은 직후, DB update 직전에 preserve 호출 추가:
     ```python
     from src.utils.preserve import preserve_selected_keys
     ...
     result = analyzer.process(article, article['agency'])
     if result:
         preserved = preserve_selected_keys(article.get('analysis_result'), result)
         update_data = {"analysis_result": preserved}
         supabase.table('articles').update(update_data).eq('id', article['id']).execute()
         ...
     ```
   - import 추가는 파일 상단 (다른 import 들 옆) 에 1 줄. `sys.path.append(project_root)` 가 이미 line 9 에 있으므로 `from src.utils.preserve import ...` 가 동작.
   - **다른 비즈니스 로직 (analyzer 호출, 카운트 변수, 로깅, 에러 처리, sleep) 은 1 줄도 건드리지 마라**.

3. **helper unit test 신설**: `tests/unit/utils/test_preserve.py`
   - `tests/unit/utils/__init__.py` 가 없으면 빈 파일로 만든다. (`tests/unit/` 는 이미 패키지 — `tests/unit/__init__.py` 존재 확인 후 진행. 없으면 작업 phase 가 깨진다는 신호.)
   - 케이스:
     - **A**: `old = {'pdf_url': 'u', 'risk_level': 'HIGH'}`, `new = {'risk_level': 'LOW', 'risk_score': 20}` → `{'risk_level': 'LOW', 'risk_score': 20, 'pdf_url': 'u'}`
     - **B**: `old = {'pdf_url': 'u'}`, `new = None` → `{'pdf_url': 'u'}`
     - **C**: `old = None`, `new = {'risk_level': 'LOW'}` → `{'risk_level': 'LOW'}`
     - **D**: `old = {'risk_level': 'HIGH'}`, `new = {'risk_level': 'LOW'}` → `{'risk_level': 'LOW'}` (preserved 키 없음)
     - **E**: `old = {'pdf_url': ''}`, `new = None` → `None` (empty string 은 carry 대상 아님)
     - **F**: `old = {'pdf_url': 'u'}`, `new = {'pdf_url': 'v'}` → `{'pdf_url': 'v'}` (new 의 값이 우선)
     - **G**: `old = "not a dict"`, `new = {'x': 1}` → `{'x': 1}` (defensive)
     - **H**: `old = {'pdf_url': 'u', 'extra': 1}`, `new = {'analysis_status': 'ANALYZED'}` → `{'analysis_status': 'ANALYZED', 'pdf_url': 'u'}` (오직 PRESERVED_KEYS 만 carry, `extra` 는 버려진다)

4. **reanalyze 스크립트 import smoke** (선택, env 의존):
   - `reanalyze_articles.py` 자체는 import 시 `load_dotenv()` 가 실행되고 `from src.db.client import supabase` 가 lazy 객체 생성 (실제 호출 없으면 env 미의존). import 자체는 실패하지 않을 가능성이 높지만, 환경 의존성을 회피하기 위해 `importlib.util.spec_from_file_location` 로 path 기반 import smoke 만 한다 (패키지화 없이):
     ```python
     # tests/unit/utils/test_reanalyze_import_smoke.py (선택; 본 phase 의 AC 에는 포함하지 않음)
     ```
   - import smoke 는 phase 5 의 AC 강제 항목이 아니다. AC 는 helper unit test 와 import 경로 grep 만 체크.

## Acceptance Criteria

```bash
# 1) helper 파일 존재 + 위치 정합
test -f src/utils/preserve.py
! test -f scripts/admin/_preserve.py        # 옛 위치에 만들지 않았는지
! test -f scripts/__init__.py               # scripts 패키지화 안 했는지
! test -f scripts/admin/__init__.py
! test -d tests/unit/scripts                # tests/unit/scripts 디렉토리 안 만들었는지

# 2) helper import 가능 + 시그니처 동작
python3 -c "from src.utils.preserve import preserve_selected_keys, PRESERVED_KEYS; assert PRESERVED_KEYS == ('pdf_url',); print(preserve_selected_keys({'pdf_url':'u'}, None))"

# 3) helper unit test 통과
python3 -m pytest tests/unit/utils/test_preserve.py -q

# 4) reanalyze_articles.py 가 preserve 를 실제로 사용하는가
grep -q "from src.utils.preserve import preserve_selected_keys" scripts/admin/reanalyze_articles.py
grep -q "preserve_selected_keys(" scripts/admin/reanalyze_articles.py

# 5) reanalyze_articles.py 가 SELECT 에 analysis_result 를 포함하는가
grep -q "select('id, title, content, agency, analysis_result')" scripts/admin/reanalyze_articles.py

# 6) 허용된 파일 외에는 변경되지 않았는가 (diff 화이트리스트)
python3 - <<'PY'
import subprocess
diff = subprocess.check_output(['git','diff','--name-only','HEAD']).decode().strip().split('\n')
diff = [f for f in diff if f]
allowed = {
    'src/utils/preserve.py',
    'scripts/admin/reanalyze_articles.py',
    'tests/unit/utils/test_preserve.py',
    'tests/unit/utils/__init__.py',  # 처음 만드는 경우만
    'tasks/8-round6-backend-safety/index.json',  # phase status 변경
}
unexpected = [f for f in diff if f not in allowed]
assert not unexpected, f"unexpected diff: {unexpected}"
print("diff scope OK")
PY

# 7) backfill script 는 1 byte 도 변경되지 않았는가 (OOS 가드)
python3 - <<'PY'
import subprocess
diff = subprocess.check_output(['git','diff','--name-only','HEAD','--','scripts/admin/run_backfill_safe.py']).decode().strip()
assert diff == '', f"run_backfill_safe.py must remain untouched in phase 5: {diff}"
print("run_backfill_safe.py untouched")
PY

# 8) 전체 단위 테스트 무회귀
python3 -m pytest tests/unit -q

# 9) phase 4 의 pipeline 테스트도 여전히 통과
python3 -m pytest tests/unit/pipeline -q
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 5 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **허용 파일 외 수정 금지**. phase 5 가 건드릴 수 있는 파일은 정확히:
  - `src/utils/preserve.py` (신규)
  - `scripts/admin/reanalyze_articles.py` (수정 — SELECT 컬럼 추가, preserve import + 호출)
  - `tests/unit/utils/test_preserve.py` (신규)
  - `tests/unit/utils/__init__.py` (없으면 신규, 빈 파일)
  - `tasks/8-round6-backend-safety/index.json` (phase status 업데이트)
  그 외 어떤 파일도 변경 금지. 특히 **`scripts/admin/run_backfill_safe.py` 와 다른 `scripts/admin/*.py` 는 1 byte 도 손대지 마라**. roadmap §11 R6 의 known limitation 으로 명시되어 있다.
- **scripts/ 패키지화 금지**. `scripts/__init__.py`, `scripts/admin/__init__.py`, `tests/unit/scripts/` 디렉토리 등 패키지 마커 일체 만들지 마라. helper 는 `src/utils/preserve.py` 에 두어 `from src.utils.preserve import ...` 만으로 import 가능 (`reanalyze_articles.py:9` 의 `sys.path.append(project_root)` 가 이미 작동 중).
- **deprecated 상수 라인 (line 13) 은 건드리지 마라**. task 10 phase 1 의 영역.
- helper 는 **순수 함수**. 외부 의존성 (`requests`, `supabase`, `dotenv` 등) import 금지.
- `PRESERVED_KEYS` 는 현재 `('pdf_url',)`. 향후 확장을 위해 tuple 로 두지만 본 phase 에서 다른 키 추가 금지.
- `setdefault` 방식 (= new 에 이미 있으면 덮지 않음) 은 의도적 선택이다. "최신 재분석" 의 의미를 유지하려면 new 가 우선.
- `src/utils/preserve.py` 의 시맨틱은 phase 4 의 `_save_item` 내부 merge 와 같은 방향이어야 한다 (양쪽 모두 "기존 pdf_url 보존, 새 값이 있으면 새 값 우선").
- 실제 `reanalyze_all()` 호출 금지. AC 는 helper unit test + grep 정합성 검사 + import smoke 까지만.
