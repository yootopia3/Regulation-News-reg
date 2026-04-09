# Phase 6: pipeline-di-refactor

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C5, §8.1 phase 4, §11 R4)
- `/home/pacer/projects/reg_brief/spec/backend-architecture.md` (Pipeline 의 의존성 방향)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/pipeline.py` 전체. 특히 L19–64 (`__init__`, `_init_analyzer`, `_init_notifier`, `_init_db`, `self.scraper = ContentScraper()`).
- `/home/pacer/projects/reg_brief/src/main.py` — `Pipeline(CONFIG_PATH).run()` 호출 방식.
- `/home/pacer/projects/reg_brief/tests/unit/pipeline/test_is_duplicate.py` — 현재 어떻게 Pipeline 을 인스턴스화하는지 확인 (해킹을 쓰는지, full init 하는지).

이전 phase의 작업물도 확인하라:

- Phase 4 의 `_save_item` 변경.
- Phase 5 의 scripts/admin 변경 (본 phase 와 무관하므로 회귀만 체크).

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `Pipeline.__init__` 에 의존성 주입 지점을 만들어 phase 7 의 run() 레벨 테스트가 가능해지게 한다. **기본 동작 (인자 없는 생성) 은 기존과 100% 동일** 해야 한다.

1. **`Pipeline.__init__` 시그니처 확장**: `src/pipeline.py`
   - 기존:
     ```python
     class Pipeline:
         def __init__(self, config_path):
             self.config_path = config_path
             self.agency_map = self._load_agency_map()
             self.analyzer = self._init_analyzer()
             self.notifier = self._init_notifier()
             self.supabase = self._init_db()
             self.scraper = ContentScraper()
     ```
   - 목표:
     ```python
     class Pipeline:
         def __init__(
             self,
             config_path,
             *,
             analyzer=None,
             notifier=None,
             db=None,
             scraper=None,
         ):
             self.config_path = config_path
             self.agency_map = self._load_agency_map()
             self.analyzer = analyzer if analyzer is not None else self._init_analyzer()
             self.notifier = notifier if notifier is not None else self._init_notifier()
             self.supabase = db if db is not None else self._init_db()
             self.scraper = scraper if scraper is not None else ContentScraper()
     ```
   - 주입되지 않은 의존성은 기존 try/except import + factory 경로를 그대로 탄다.
   - 주입된 의존성은 그 객체를 그대로 사용한다. 별도 검증 (isinstance 등) 금지.
   - 모든 새 파라미터는 **keyword-only** (`*,` 뒤). 기존 positional `config_path` 는 유지.

2. **`src/main.py` 는 수정 금지**. 기존대로 `Pipeline(CONFIG_PATH).run()` 호출이 동작해야 한다.

3. **`_init_*` 메서드 자체는 수정 금지**. 그대로 호출 가능한 상태로 남겨둔다. 본 phase 는 생성자 라인만 고치는 최소 변경이다.

4. **새 테스트 케이스 (간단한 DI smoke)**:
   - `tests/unit/pipeline/test_di_smoke.py` 신설 (or `test_is_duplicate.py` 에 추가하지 말 것 — 분리 유지).
   - 케이스: `Pipeline('config/agencies.json', analyzer='MARKER_A', notifier='MARKER_N', db='MARKER_D', scraper='MARKER_S')` 로 생성 후 `pipeline.analyzer == 'MARKER_A'`, `pipeline.notifier == 'MARKER_N'`, `pipeline.supabase == 'MARKER_D'`, `pipeline.scraper == 'MARKER_S'` 검증.
   - 케이스: `Pipeline('config/agencies.json')` 로 생성할 때 analyzer/notifier/db/scraper 가 `None` 은 아닐 수도 있음 (import 실패 시 None 가능) — 이 케이스에서 **AttributeError 없이 생성 자체는 성공** 하는지 확인. 구체 타입 assertion 은 하지 않는다 (환경 의존).
   - **중요**: `'MARKER_A'` 같은 dummy 값을 쓰는 이유는, 본 phase 가 `ContentScraper` 같은 실제 타입 의존성을 주입 지점에서 검증하지 않기 때문이다. phase 7 에서 실제 fake 객체를 쓴다.

5. **기존 테스트 무회귀**:
   - `tests/unit/pipeline/test_is_duplicate.py` 가 Pipeline 을 어떻게 만들고 있는지 먼저 확인. 만약 `Pipeline.__new__(Pipeline)` + 속성 직접 세팅 방식이면 영향 없음. 만약 `Pipeline(config_path)` 를 직접 호출하면, 새 시그니처 호환성이 유지되므로 역시 영향 없음.
   - 실행해서 통과 확인.

## Acceptance Criteria

```bash
# 1) 기본 생성 smoke (인자 없이)
python3 -c "from src.pipeline import Pipeline; p = Pipeline('config/agencies.json'); print('default init OK:', type(p).__name__)"

# 2) DI 생성 smoke
python3 -c "from src.pipeline import Pipeline; p = Pipeline('config/agencies.json', analyzer='A', notifier='N', db='D', scraper='S'); assert p.analyzer=='A' and p.notifier=='N' and p.supabase=='D' and p.scraper=='S'; print('DI init OK')"

# 3) 신규 DI smoke 테스트 통과
python3 -m pytest tests/unit/pipeline/test_di_smoke.py -q

# 4) 기존 pipeline 테스트 무회귀
python3 -m pytest tests/unit/pipeline -q

# 5) 전체 단위 테스트 무회귀
python3 -m pytest tests/unit -q

# 6) main.py 는 수정되지 않았는가
python3 - <<'PY'
import subprocess
diff = subprocess.check_output(['git','diff','--name-only','HEAD','--','src/main.py']).decode().strip()
assert diff == '', f"src/main.py should not be modified: {diff}"
print("main.py untouched")
PY
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 6 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **default 동작 불변**. 인자 없이 생성했을 때 `self.analyzer` 등이 기존과 완전히 동일한 경로로 설정되어야 한다. `_init_*` 의 try/except 로직을 조금도 수정하지 마라.
- 새 파라미터는 **반드시 keyword-only**. positional 로 받으면 `config_path` 다음 순서에 어떤 객체를 넣었는지 호출부에서 헷갈린다.
- 주입된 의존성에 대한 validation (isinstance, duck typing, attr 확인) 금지. 테스트 책임.
- `src/main.py` 수정 금지. 운영 엔트리 포인트는 그대로 두어 회귀 위험을 최소화.
- `_init_*` 내부의 try/except import 는 DI 목적에 방해처럼 보이지만 건드리지 마라. round 1 에서 의도적으로 넣은 lazy guard다 (`.env` 없이 import 가능해야 한다는 제약).
- `test_di_smoke.py` 의 목적은 "DI 지점이 실제로 있다" 는 minimal proof 이지 run() 레벨 테스트가 아니다. phase 7 에서 진짜 테스트가 쓰인다.
- 리턴 타입 annotation 추가 금지 (scope 밖). 기존 스타일 그대로 유지.
