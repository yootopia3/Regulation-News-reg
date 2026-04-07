# Phase 1: backend-hygiene

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `CLAUDE.md` — phase 실행/커밋/네이밍 규약.
- `spec/refactor-round1.md` — round 1 회귀 체크리스트(§4, §6.1). "import 사이드이펙트 0" 원칙은 그대로 유지된다.
- `spec/backend-architecture.md` §6 — round 1에서 정리한 import-time side effect 제거 표. 본 phase는 그 표를 깨뜨리지 않는 선에서 동작한다.

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. **source-first** 다:

- `src/collectors/rss_parser.py` — `print()` 잔존 8곳(L62, 91, 97, 101, 108, 113, 176, 178). 모듈 상단(L10)에 이미 `logger = logging.getLogger(__name__)` 가 정의되어 있다.
- `src/services/notifier.py` — `print()` 잔존 4곳(L16, 25, 35, 37). 모듈에 logger가 아직 정의되지 않았다. L33에 `verify=False` 가 박혀 있다(주석 `# Debug: verify=False`).
- `src/utils/logger.py` — L4: `from src.services.notifier import TelegramNotifier`(이 줄은 건드리지 마라), L5: `from config import settings`(이 줄만 정정 대상). `setup_logger()` 가 `src` 패키지 logger에 핸들러를 부착해 두어, 본 phase가 추가하는 module-level logger가 자동으로 그 산하로 들어간다.
- `src/config/settings.py` — `LOG_FILE_PATH`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT` 가 정의되어 있는지 직접 확인. 새 import 경로가 동작하는 단일 진입점이다.
- `src/config/__init__.py` — 패키지 import가 가능한지 확인.

이전 phase 산출물:

- 본 task의 첫 phase이므로 이전 phase 산출물은 없다.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하라.

## 작업 내용

본 phase는 백엔드 only. 외부 동작 변경 0건. 메시지 텍스트 의미 변경 0건.

### 1. `src/collectors/rss_parser.py` 의 `print()` → `logger`

- 모듈 상단에 이미 정의된 `logger`(L10)를 그대로 사용. 새 logger 인스턴스 생성 금지.
- 8곳 모두 다음 매핑으로 치환:
  - 진행 상태 알림(예: `"Fetching RSS for ..."`, `"> Found N items."`) → `logger.info(...)`
  - 비치명 경고(예: `"> No entries found in feed."`, `"> Warning: Feed parsing issue ..."`, `"> Error processing URL ... after N attempts: ..."`) → `logger.warning(...)`
  - exception 메시지(예: `"> Error processing URL {target_url}: {e}"`, `"> Error fetching {agency['name']}: {e}"`) → `logger.error(...)`
- **메시지 텍스트(따옴표 내부 문자열) 변경 금지.** f-string/포맷 인자도 그대로 유지.
- 기존 `logger.warning(...)` 호출(L83-89, L159-164)은 그대로 두고, 새로 추가만 한다.

### 2. `src/services/notifier.py` 의 `print()` → `logger` + `verify=False` 제거

- 파일 최상단 import 영역에 다음 두 줄을 추가:
  ```python
  import logging
  ```
  그리고 `class TelegramNotifier:` 선언 직전(또는 import 블록 마지막)에:
  ```python
  logger = logging.getLogger(__name__)
  ```
- 4곳 치환:
  - L16 `print("Warning: Telegram credentials not set.")` → `logger.warning("Telegram credentials not set.")`
  - L25 `print("Telegram notification disabled (missing credentials).")` → `logger.warning("Telegram notification disabled (missing credentials).")`
  - L35 `print("Telegram message sent successfully.")` → `logger.info("Telegram message sent successfully.")`
  - L37 `print(f"Error sending Telegram message details: {type(e).__name__}: {e}")` → `logger.error(f"Error sending Telegram message details: {type(e).__name__}: {e}")`
- **L33의 `verify=False` 인자를 제거.** `requests.post(self.base_url, data=payload, timeout=20, verify=False)` → `requests.post(self.base_url, data=payload, timeout=20)`. 같은 줄의 `# Debug: verify=False` 주석도 함께 제거.
- `if __name__ == "__main__":` 블록(L59-65) 의 `traceback.print_exc()` 는 logger 대상이 아니라 stdout 디버그 진입점이다. **건드리지 마라.**

### 3. `src/utils/logger.py` 의 레거시 import 경로 정정

- L5 `from config import settings` 한 줄을 `from src.config import settings` 로 교체.
- 그 외 어떤 변경도 금지. 특히 L4 `from src.services.notifier import TelegramNotifier` 는 그대로 둔다(utils → services 의존 역방향 정리는 본 round의 out-of-scope).
- 교체 후 `settings.LOG_FILE_PATH`, `settings.LOG_MAX_BYTES`, `settings.LOG_BACKUP_COUNT` 참조가 그대로 동작하는지 import smoke로 자가검증.

## Acceptance Criteria

```bash
# 1. backend import smoke (.env 없이 import 부작용 0)
venv/bin/python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"

# 2. 두 파일에서 print() 잔존 0건
test -z "$(grep -nE '^[^#]*\bprint\(' src/collectors/rss_parser.py src/services/notifier.py)"

# 3. notifier.py 의 verify=False 잔존 0건
test -z "$(grep -n 'verify=False' src/services/notifier.py)"

# 4. logger.py 의 레거시 import 0건
test -z "$(grep -n 'from config import settings' src/utils/logger.py)"

# 5. logger.py 가 src.config 경로를 사용
grep -q 'from src.config import settings' src/utils/logger.py

# 6. notifier.py 에 module-level logger 가 도입됨
grep -q 'logger = logging.getLogger(__name__)' src/services/notifier.py

# 7. task 단위 build_command (백엔드 + 프론트 둘 다 통과)
venv/bin/python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer" && cd web && npm run build
```

## AC 검증 방법

위 7개 커맨드를 순서대로 직접 실행하라. 모두 통과하면 `tasks/3-auth-hardening/index.json` 의 phase 1 status를 `"completed"` 로 변경하라.

수정 3회 이상 시도해도 실패하면 status를 `"error"` 로 변경하고, `error_message` 필드에 어떤 검증 단계가 어떤 출력으로 실패했는지 기록하라.

작업 중 사용자 개입이 반드시 필요한 상황(`venv/` 자체가 없거나 dependencies 미설치, `npm install` 미수행 등)이 발생하면 status를 `"blocked"` 로, `blocked_reason` 에 사유를 기록하고 즉시 중단하라.

## 주의사항

- `src/config/settings.py:48` 의 `SSL_VERIFY = False` 와 `src/collectors/http.py` 의 SSL 정책은 **건드리지 마라**. 이유: collector 전역 SSL 정책 개편은 본 라운드의 명시적 out-of-scope이며, 일부 KR 정부 사이트 호환을 위한 의도적 설정일 가능성이 있다.
- `setup_logger()` 시그니처/로직, `TelegramLoggingHandler`, telegram 핸들러의 부착 위치(legacy logger only)를 **변경하지 마라**. 이유: notifier/logger 의존 구조 재설계는 out-of-scope.
- `scripts/debug/**` 의 `print` / `verify=False` 는 **본 phase 대상이 아니다**. 정리 금지.
- `print()` 호출의 메시지 텍스트(따옴표 내부 문자열, f-string 본문, 포맷 인자)를 **변경하지 마라**. grep diff 가능성을 보존해야 한다.
- `rss_parser.py` 의 `parse_date`, RSS 재시도 정책(`RSS_FETCH_MAX_ATTEMPTS`, `RSS_FETCH_RETRY_BACKOFF_SECONDS`), stale-source 경고 로직, `feedparser.parse` 흐름은 **건드리지 마라**.
- 새 logger 핸들러 부착, 로깅 포맷 변경, 로그 레벨 정책(`logging.INFO` 기본) 변경 금지.
- `notifier.py` 의 `class TelegramNotifier` 메서드 시그니처(`__init__`, `send_message`, `format_and_send`) 변경 금지.
- 본 phase에서 `web/`, `db/`, `docs/`, `README.md`, `package.json` 파일을 수정하지 마라.
- 기존 테스트가 있다면 깨뜨리지 마라(현재 `tests/` 디렉토리는 없음).
