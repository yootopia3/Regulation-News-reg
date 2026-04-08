# Phase 3: python-test-harness

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (§4 회귀 체크리스트, §6 AC — 기존 import 규약)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first — 테스트 대상 함수의 실제 입출력을 코드에서 확인한 뒤 테스트를 작성하라. 머릿속 추정으로 쓰지 마라.**

- `src/collectors/date_parser.py`
- `src/collectors/pagination.py`
- `src/collectors/sanction_scraper.py` (특히 `extract_sanction_key`)
- `src/services/analyzer/safeguards.py` (특히 `apply_keyword_safeguards`)
- `src/services/analyzer/result_mapper.py`
- `src/config/settings.py` (import 사이드이펙트 없음 확인)
- `requirements.txt`

이전 phase 산출물:

- Phase 1: `.env.example`, `web/.env.local.example`, `.gitignore` 스코프 패턴
- Phase 2: `.pre-commit-config.yaml`, `.gitleaks.toml`, `.github/workflows/ci.yml` (gitleaks job만 존재)

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **pytest 하네스 + 순수 함수 단위 테스트 + CI python job 추가**만 다룬다. `src/` 코드 수정 금지.

### 1. `requirements-dev.txt` 신규

```
pytest>=7.4
pytest-mock>=3.12
```

`requirements.txt`에는 **추가하지 말 것**. dev 전용 분리.

### 2. pytest 설정

`pyproject.toml`이 없다면 신규 생성하되 pytest 섹션만 둔다. 기존 `pyproject.toml`이 존재하면 해당 섹션만 추가.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers"
```

### 3. 테스트 디렉토리 구조

```
tests/
  __init__.py
  conftest.py
  unit/
    __init__.py
    collectors/
      __init__.py
      test_date_parser.py
      test_pagination.py
      test_sanction_scraper.py
    analyzer/
      __init__.py
      test_safeguards.py
      test_result_mapper.py
```

### 4. `tests/conftest.py`

`sys.path` 조정은 pytest가 rootdir 기준으로 알아서 하지만, 명시적으로 프로젝트 루트를 `sys.path[0]`에 두어 `from src...` import가 모든 테스트에서 동작하도록 보장하라.

env 격리: `GEMINI_API_KEY` 등 실제 secret이 설정돼 있어도 테스트에서 사용되지 않도록, 테스트 시작 시 `os.environ.pop('GEMINI_API_KEY', None)` 같은 fixture를 둘 수 있다. 단 순수 함수 테스트만 다루므로 env에 의존하는 테스트는 쓰지 않는다.

### 5. 테스트 파일 — 원칙

- **순수 함수만.** 네트워크/DB/Gemini/파일시스템 외부 상태에 접근하는 테스트 금지.
- **스냅샷 스타일.** 현재 코드의 동작을 박제한다. 코드가 이상해 보여도 수정하지 말고 `# TODO(round2)` 주석만 남기고 그대로 테스트한다.
- **각 파일 최소 happy-path 1개 + edge case 1개.**
- 테스트가 Python 3.10에서 동작해야 한다 (GitHub Actions pin).

### 5-1. `tests/unit/collectors/test_date_parser.py`

`src/collectors/date_parser.py`를 읽고 그 파일이 export하는 함수(`parse_date` 등)에 대해 happy-path와 파싱 실패 케이스를 작성하라. 실제 시그니처는 코드에서 확인.

### 5-2. `tests/unit/collectors/test_pagination.py`

`src/collectors/pagination.py`가 export하는 함수(페이지 URL 생성 등)에 대해 `pageIndex`/`curPage` 분기, 1페이지·N페이지 케이스를 검증.

### 5-3. `tests/unit/collectors/test_sanction_scraper.py`

`extract_sanction_key` 함수에 대해:

- FSS 제재 공시 URL에서 `(examMgmtNo, emOpenSeq)` 튜플을 정확히 추출하는 happy case
- query string이 없는 URL → `(None, None)` 또는 현재 코드가 반환하는 실패값
- 쿼리 파라미터가 일부만 있는 URL → 현재 코드 동작 그대로

실제 반환 형식은 함수 코드에서 확인하라. 이 테스트가 Phase 6의 기반이 된다.

### 5-4. `tests/unit/analyzer/test_safeguards.py`

`apply_keyword_safeguards(title, original_score, rules)`:

- rules에 매칭되는 키워드가 있는 title → 점수 boost
- 매칭 없는 title → 원래 점수 그대로
- `config/safeguard_keywords.json`을 직접 import하지 말고, 테스트 내부에 작은 rule dict를 만들어 주입

### 5-5. `tests/unit/analyzer/test_result_mapper.py`

`result_mapper`가 export하는 함수(Gemini raw 결과 → 내부 JSON 키 변환)에 대해 현재 매핑을 박제한다. 분석 결과 JSON 키 셋(`risk_level`, `risk_score`, `summary`, `impact_analysis`, `action_items`, `pillars`, `risk_tags`, `analyzed_by`, `analysis_status`, `is_relevant`, `importance_score`, `filter_status`)이 변경되지 않는지 검증.

### 6. `.github/workflows/ci.yml` 확장

Phase 2에서 만든 `ci.yml`에 `python-test` job을 추가한다. `gitleaks` job은 그대로 두고 jobs 맵에 append.

```yaml
  python-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: python -m pytest -q
```

## Acceptance Criteria

```bash
# requirements-dev.txt 존재
test -f requirements-dev.txt
# pytest 설정 존재 (pyproject.toml 또는 pytest.ini)
grep -q 'tool.pytest.ini_options' pyproject.toml 2>/dev/null || test -f pytest.ini
# 테스트 디렉토리 구조
test -f tests/conftest.py
test -f tests/unit/collectors/test_date_parser.py
test -f tests/unit/collectors/test_pagination.py
test -f tests/unit/collectors/test_sanction_scraper.py
test -f tests/unit/analyzer/test_safeguards.py
test -f tests/unit/analyzer/test_result_mapper.py
# pytest 실행
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
# CI yml에 python-test job 추가 확인
grep -q 'python-test:' .github/workflows/ci.yml
grep -q 'python -m pytest' .github/workflows/ci.yml
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 3 status를 `"completed"`로 변경.

pytest가 실패하면 테스트 코드를 먼저 의심하라. `src/` 코드는 수정 금지다. 테스트가 현재 동작을 잘못 추정한 것이다 — 소스를 다시 읽고 실제 반환값에 맞춰 assertion을 수정하라.

3회 이상 실패 시 `"error"` + `error_message`에 최종 pytest 출력 요약. 사용자 개입 필요 시 `"blocked"`.

## 주의사항

- **`src/` 코드 수정 금지.** 테스트가 실패하면 테스트를 고쳐라.
- **네트워크·DB·Gemini·파일시스템 I/O를 요구하는 테스트 금지.** 순수 함수만.
- **Supabase 통합 테스트 금지.** `Pipeline._is_duplicate` 테스트는 Phase 6의 범위다. 여기서 미리 쓰지 마라.
- **`web/` 테스트는 Phase 4의 범위.** 이번 phase에서 vitest·web 테스트 건드리지 마라.
- **`requirements.txt`에 pytest 추가 금지.** 프로덕션 의존성이 아니다.
- **Python 3.10 호환 필수.** walrus 이상은 OK, 3.11+ 전용 기능(`StrEnum`, `Self` 등) 사용 금지.
- `logging.basicConfig`, `genai.configure` 같은 import 시 사이드이펙트가 있는 모듈을 테스트에서 가볍게 건드리지 마라 — `refactor-round1.md` 회귀 체크리스트 규약 위반이다.
- CI yml 기존 `gitleaks` job 삭제·변경 금지. append만.
- 기존 `news_collector*.yml`, `watchdog.yml` 수정 금지.
