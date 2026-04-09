# Phase 8: rss-parser-test

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C4, §8.1 phase 6)
- `/home/pacer/projects/reg_brief/spec/moef-source-round2.md` (MOEF stale warn 도입 배경)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py` 전체. 특히:
  - `parse_date(date_str)` — RFC 822 + fallback 없음.
  - `fetch_rss_feed(agency)` — URL 선택 (`url` or `rss_url`), `requests.get` 직접 호출, `RSS_FETCH_MAX_ATTEMPTS=3`, `RSS_FETCH_RETRY_BACKOFF_SECONDS=(3.0, 5.0)`, `ConnectionError/Timeout` 재시도, 그 외 예외는 즉시 빈 리스트, feedparser 파싱, FSC `%Y-%m-%d %H:%M:%S` fallback, `RSS_STALE_WARN_DAYS=14` 경고.
  - `collect_all_rss()` — 단순 wrapper.
- `/home/pacer/projects/reg_brief/tests/unit/collectors/test_date_parser.py` / `test_pagination.py` / `test_sanction_scraper.py` — 기존 collectors 테스트 스타일 참고.

이전 phase의 작업물도 확인하라:

- Phase 3 에서 rss_parser 에 `verify=get_ssl_verify(...)` 가 추가되었을 가능성. 해당 수정이 있다면 mock 의 `requests.get` 인자 검사에도 포함한다.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `src/collectors/rss_parser.py` 를 **프로덕션 코드 수정 없이** 단위 테스트로 커버한다.

1. **신규 테스트 파일**: `tests/unit/collectors/test_rss_parser.py`

2. **테스트 케이스 (최소)**:

   **T1. `parse_date` 성공 케이스 (RFC 822)**:
   - 입력: `'Tue, 03 Apr 2026 14:30:00 +0900'`
   - 기대: KST timezone aware datetime, year/month/day/hour 확인.

   **T2. `parse_date` 실패 케이스**:
   - 입력: 빈 문자열, `None`, `'not a date'` → 모두 `None` 반환.

   **T3. `fetch_rss_feed` 성공 (mocked)**:
   - `requests.get` 을 `monkeypatch` 로 mock. 200 응답 + 유효 RSS XML content (2 entries).
   - `feedparser.parse` 는 mock 하지 않고 실제로 동작하게 한다 (XML string 파싱).
   - 결과: 2개 item, 각 item 의 `agency`, `title`, `link`, `published_at` 채워짐.

   **T4. `fetch_rss_feed` — method 가 scraper 이면 skip**:
   - agency dict 에 `collection_method='scraper'` → 빈 리스트 반환 (mock 없이).

   **T5. `fetch_rss_feed` — ConnectionError 1회 후 성공**:
   - `requests.get` 을 첫 호출에는 `ConnectionError` raise, 두 번째 호출에는 200 응답 반환하도록 mock.
   - `time.sleep` 도 mock (테스트 시간 절약).
   - 결과: 성공 경로. 호출 횟수 2회.

   **T6. `fetch_rss_feed` — 재시도 소진**:
   - `requests.get` 이 매번 `ConnectionError` raise.
   - 결과: 빈 리스트. 호출 횟수 `RSS_FETCH_MAX_ATTEMPTS == 3`.

   **T7. `fetch_rss_feed` — HTTP 4xx 즉시 실패 (재시도 없음)**:
   - `requests.get` 이 200 을 돌려주되 `response.raise_for_status` 가 HTTPError raise. (mock: `mock_response.raise_for_status = Mock(side_effect=HTTPError)`).
   - 결과: 빈 리스트. 호출 횟수 1 (재시도 금지).

   **T8. `fetch_rss_feed` — stale warning 발동**:
   - RSS XML 에 entries 가 있고, 모든 entry 의 날짜가 `RSS_STALE_WARN_DAYS + 5` 일 (예: 19일) 이전.
   - `caplog` 를 써서 warning 레벨 로그에 `[STALE RSS]` 문자열이 포함되는지 확인.
   - parse 성공 경로이므로 parsed_items 는 여전히 반환된다.

   **T9. `fetch_rss_feed` — stale warning 미발동 (fresh)**:
   - 최신 entry 가 오늘 날짜 → `[STALE RSS]` 경고 없음.

   **T10. (선택) `parse_date` FSC 포맷**:
   - `fetch_rss_feed` 의 FSC fallback `'2026-01-02 00:00:00'` 파싱 경로 — feedparser + fallback strptime 이 정상 동작하는지 RSS XML 에 해당 형식을 넣어 E2E 검증.

3. **mock 전략**:
   - `monkeypatch.setattr('src.collectors.rss_parser.requests.get', fake_get)` 로 `requests.get` 교체. **주의**: `rss_parser.py` 안에서 `import requests` 를 하는 방식에 따라 patch target 이 달라질 수 있다. 파일을 열어 import 스타일 확인 후 정확한 경로 사용.
   - `monkeypatch.setattr('src.collectors.rss_parser.time.sleep', lambda s: None)` 로 재시도 백오프 무시.
   - `caplog.set_level(logging.WARNING, logger='src.collectors.rss_parser')` 로 경고 캡처.

4. **fixture 데이터**:
   - RSS XML 은 테스트 파일 상단에 문자열 상수로 정의. 외부 파일 쓰지 마라.
   - 예:
     ```python
     RSS_XML_FRESH = b"""<?xml version="1.0" encoding="UTF-8"?>
     <rss version="2.0"><channel><title>Test</title>
     <item><title>Item A</title><link>https://example.com/a</link>
     <pubDate>Tue, 08 Apr 2026 09:00:00 +0900</pubDate></item>
     ...
     </channel></rss>"""
     ```

## Acceptance Criteria

```bash
# 1) 테스트 파일 존재
test -f tests/unit/collectors/test_rss_parser.py

# 2) 신규 테스트 통과
python3 -m pytest tests/unit/collectors/test_rss_parser.py -q

# 3) 기존 collectors 테스트 무회귀
python3 -m pytest tests/unit/collectors -q

# 4) 전체 단위 테스트 무회귀
python3 -m pytest tests/unit -q

# 5) rss_parser 프로덕션 코드가 수정되지 않았는가
python3 - <<'PY'
import subprocess
diff = subprocess.check_output(['git','diff','--name-only','HEAD','--','src/collectors/rss_parser.py']).decode().strip()
if diff:
    # phase 3 에서 이미 한 번 수정되었을 수 있으므로, 그 경우엔 현재 phase 의 HEAD 가 아닌 이전 phase commit 과 비교해야 함.
    # 대신 이 체크는 수동 검토로 돌리고 pass 처리.
    print("NOTE: rss_parser.py was modified in a prior phase (expected if phase 3 ran).")
else:
    print("rss_parser.py clean since last commit")
PY

# 6) time.sleep / requests.get 이 mock 된 상태로만 테스트가 동작하는지 (테스트 실행이 10초 이내)
python3 -m pytest tests/unit/collectors/test_rss_parser.py --durations=10 -q
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 8 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **production 코드 수정 금지**. `src/collectors/rss_parser.py` 는 이 phase 에서 건드리지 마라. 오직 `tests/unit/collectors/test_rss_parser.py` 1 파일 신설.
- `time.sleep` 을 반드시 mock 하라. 재시도 2회 중 첫 번째 실패 시 3초, 두 번째 5초 = 총 8초 대기는 테스트 속도를 망친다.
- `feedparser.parse` 는 mock 하지 말고 실제로 돌려라. RSS XML 파싱이 실제 라이브러리 동작에 의존하는 것을 테스트가 보존해야 한다.
- `caplog` 를 사용할 때 logger 이름을 정확히 지정 (`src.collectors.rss_parser`). 모듈 상단에서 `logger = logging.getLogger(__name__)` 로 만들어진 이름과 일치.
- `RSS_STALE_WARN_DAYS` 값 자체는 하드코딩하지 말고 `from src.collectors.rss_parser import RSS_STALE_WARN_DAYS` 로 읽어 `+ 5` 같은 오프셋을 쓴다 (상수가 바뀌어도 테스트 견고).
- T5 / T6 의 `RSS_FETCH_MAX_ATTEMPTS` 도 동일하게 import 로 참조.
- `requests.get` 호출 인자에 `verify=` 가 포함될 수 있다 (phase 3 에서 SSL opt-in 이 적용되었으면). mock 은 이 kwarg 를 수용해야 하지만, 테스트 어설션은 `verify` 값을 강제하지 말 것 (phase 3 결과에 의존) — 단순히 call 이 있었는지만 검증.
- 실제 네트워크 호출 **절대 금지**. `requests.get` 이 mock 되지 않은 경로가 있으면 테스트가 외부 네트워크에 의존하게 된다.
