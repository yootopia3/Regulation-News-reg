# Phase 2: Settings & Agency Constants

설정·환경변수 로딩과 agency 코드를 한 군데로 모은다. 호출부 치환만, 동작 동일.

## 사전 준비

먼저 설계 의도를 읽어라:

- `spec/refactor-round1.md` — 라운드 scope, AC, 회귀 체크리스트
- `spec/backend-architecture.md` — phase 1에서 작성한 설계 (특히 §5 enum 계획,
  §6 side effect 제거 계획)

핵심 소스를 직접 읽어라:

- `config/settings.py` — 현재 상수
- `src/db/client.py` — `os.environ.get` 직접 사용
- `src/services/analyzer.py` — `load_dotenv`, `os.getenv`, `from config.settings import ...`
- `src/services/notifier.py` — `load_dotenv`, `os.getenv`
- `src/collectors/rss_parser.py` — `from config import settings`
- `src/collectors/scraper.py` — `from config import settings`
- `src/pipeline.py` — `'FSS_SANCTION'`, `'FSS_MGMT_NOTICE'` 리터럴 사용 위치

이전 phase 산출물:

- `spec/backend-architecture.md`

## 작업 내용

### 2.1 `src/config/` 모듈 신설

- `src/config/__init__.py`
- `src/config/settings.py` — 새 모듈. 다음 책임만 갖는다:
  - 모듈 import 시 사이드 이펙트 없음 (top-level에서 `load_dotenv` 호출 금지).
  - `load_env(path: Path | None = None) -> None` — 명시 호출 시점에 `.env` 1회
    로드. 멱등.
  - 환경변수 접근 함수: `get_supabase_url() -> str`, `get_supabase_anon_key() -> str`,
    `get_gemini_api_key() -> str`, `get_telegram_bot_token() -> str | None`,
    `get_telegram_chat_id() -> str | None`. 필수값은 없으면 `RuntimeError`. 옵션
    값은 `None` 반환.
  - 기존 `config/settings.py`에 있던 모든 상수를 그대로 옮긴다 (`MODEL_FILTER_ID`,
    `MODEL_ANALYZER_ID`, `MODEL_ANALYZER_FALLBACK`, `IMPORTANCE_THRESHOLD`,
    `API_CALL_DELAY`, `USER_AGENT`, `SCRAPER_TIMEOUT`, `SCRAPER_RETRY_DELAY_MIN`,
    `SCRAPER_RETRY_DELAY_MAX`, `SSL_VERIFY`, `SUPPRESS_SSL_WARNINGS`,
    `COLLECTION_INTERVAL_MINUTES`, `LOG_FILE_PATH`, `LOG_MAX_BYTES`,
    `LOG_BACKUP_COUNT`). 값 변경 금지.
  - `CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"`
    상수와 `AGENCIES_JSON_PATH`, `SAFEGUARD_KEYWORDS_PATH` 헬퍼 path를 노출.

### 2.2 기존 `config/settings.py` 호환 shim

- 기존 `config/settings.py`는 **삭제하지 말고**, `src.config.settings` 의 모든
  상수를 re-export 하는 shim으로 축소한다 (`from src.config.settings import *`).
  이번 라운드에서 호출부를 한 번에 못 바꿀 가능성을 대비한다.
- shim에서도 `load_dotenv` 호출 금지.

### 2.3 `src/config/agency_codes.py` 신설

- `class AgencyCode(str, Enum)` 정의. 멤버: `FSC`, `MOEF`, `FSS`, `BOK`,
  `FSS_REG`, `FSC_REG`, `FSS_REG_INFO`, `FSS_SANCTION`, `FSS_MGMT_NOTICE`. 값은
  소스 문자열과 정확히 동일.
- `SANCTION_AGENCY_CODES: frozenset[AgencyCode] = frozenset({FSS_SANCTION,
  FSS_MGMT_NOTICE})` 노출.
- `class ArticleCategory(str, Enum)` 정의. 멤버: `PRESS_RELEASE='press_release'`,
  `REGULATION_NOTICE='regulation_notice'`, `SANCTION_NOTICE='sanction_notice'`.
- 두 enum 모두 `str` 상속이라 기존 문자열 비교/DB 저장이 그대로 동작해야 한다.

### 2.4 호출부 치환

다음 위치에서 문자열 리터럴 → enum 치환:

- `src/pipeline.py`의 `'FSS_SANCTION'`, `'FSS_MGMT_NOTICE'` 분기 (모두) →
  `AgencyCode.FSS_SANCTION`, `AgencyCode.FSS_MGMT_NOTICE` 또는
  `SANCTION_AGENCY_CODES` 사용.
- `src/services/analyzer.py`의 `from config.settings import ...` →
  `from src.config.settings import ...` 로 변경 (shim도 동작하지만 새 경로 우선).
- `src/services/notifier.py`, `src/db/client.py`의 `load_dotenv` + `os.getenv`
  직접 호출 → `src.config.settings.load_env()` + getter 사용.
- `src/collectors/rss_parser.py`, `src/collectors/scraper.py`의
  `from config import settings` → `from src.config import settings` 로 변경
  (값 사용 방식 동일).
- `src/main.py`에서 프로그램 진입 시점에 `load_env()`를 명시 호출.

### 2.5 import 사이드 이펙트 제거

- `src/services/analyzer.py` 모듈 top-level의 `load_dotenv(...)` 호출과
  `logging.basicConfig(...)` 호출 제거. `genai.configure(...)`는 이번 phase에서는
  유지하되, **`HybridAnalyzer.__init__` 안에서만 호출되도록** 옮긴다 (이미 그
  자리에서도 호출되고 있는지 확인하고, top-level 호출이 있으면 제거).
- `config/settings.py` (shim) 도 top-level 사이드 이펙트 0건 확인.

## Acceptance Criteria

```bash
# 새 모듈 존재
test -f src/config/__init__.py
test -f src/config/settings.py
test -f src/config/agency_codes.py

# import 사이드 이펙트 없음
python -c "import src.config.settings; import src.config.agency_codes"
python -c "from src.services.analyzer import HybridAnalyzer"  # genai.configure 호출 안 됨
python -c "from src.services import notifier"

# enum 치환 확인 — pipeline.py에 sanction agency 문자열 리터럴 0건
! grep -n "'FSS_SANCTION'" src/pipeline.py
! grep -n "'FSS_MGMT_NOTICE'" src/pipeline.py

# 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 명령을 모두 실행하라. 통과 시 `tasks/1-backend-structure/index.json`의 phase 2
status를 `"completed"`로 변경하라.

3회 이상 실패 시 `"error"` + `error_message` 기록.

## 주의사항

- **상수 값 변경 금지.** 옮기기만 해라.
- **`config/settings.py` 삭제 금지.** shim으로 유지한다. 기존 import 경로
  (`from config import settings`) 가 깨지지 않게 하라.
- `agencies.json` 의 데이터 구조나 키 이름은 건드리지 마라. enum은 코드 안에서만
  사용한다.
- `AgencyCode`는 `str` 상속이라 `agency_config.get('code') == AgencyCode.FSC` 같은
  비교가 동작해야 한다. 만약 안 되면 `.value`를 명시적으로 비교하거나
  `AgencyCode(agency_config['code'])` 변환을 사용하라.
- `analyzer.py`의 `genai.configure`를 함수 안으로 옮길 때 인스턴스가 매번 호출돼도
  안전해야 한다 (genai SDK는 멱등). 의문이 있으면 옮기지 말고 phase 4에서
  처리하라.
- DB 스키마, `web/`, `agencies.json`, `.github/`, `scripts/`, 루트 dump 파일 diff 0건.
