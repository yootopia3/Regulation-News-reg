# Phase 5: Scraper Decompose

`src/collectors/scraper.py` (453 LOC) 를 책임별로 분해한다. 리스트 스크래퍼,
본문 fetcher, 제재 스크래퍼, 날짜 파서, HTTP 세션이 한 클래스에 뭉쳐 있다.

## 사전 준비

설계 의도:

- `spec/refactor-round1.md` — agency 동작/cutoff 동일 유지
- `spec/backend-architecture.md` — `src/collectors/` 목표 구조

핵심 소스:

- `src/collectors/scraper.py` 전체 (453 LOC)
- `src/collectors/rss_parser.py` (변경 없음, 호출 흐름 확인용)
- `src/pipeline.py` — `self.scraper.fetch_list_items(...)`,
  `self.scraper.fetch_content(...)`, `self.scraper.fetch_sanction_items(...)` 호출부
- `config/agencies.json` — selector 구조 (변경 금지)

이전 phase 산출물:

- `src/config/settings.py` (phase 2)
- `src/config/agency_codes.py` (phase 2)
- `spec/backend-architecture.md`

## 작업 내용

### 5.1 새 모듈 분해

```
src/collectors/
  __init__.py
  rss_parser.py          # 그대로 (import 경로만 정리)
  http.py                # 신규
  date_parser.py         # 신규
  pagination.py          # 신규
  list_scraper.py        # 신규
  content_scraper.py     # 신규
  sanction_scraper.py    # 신규
  scraper.py             # facade — backward compat
```

### 5.2 `http.py`

- `def get_session() -> requests.Session` — 모듈 레벨에 단일 Session 인스턴스를
  lazy 생성·캐싱. 기본 헤더는 현재 `ContentScraper.__init__` 의 dict 그대로.
- `def fetch(url: str, *, timeout: int | None = None) -> requests.Response` —
  `get_session().get(url, timeout=timeout or SCRAPER_TIMEOUT, verify=SSL_VERIFY)`.
  `raise_for_status()` 호출. retry 없음 (호출부 기존 로직 유지).
- `SUPPRESS_SSL_WARNINGS` 처리(`urllib3.disable_warnings`)를 이 모듈로 이동. 단,
  모듈 import 시점이 아니라 `get_session()` 첫 호출 시점에 1회만 실행.

### 5.3 `date_parser.py`

- `KST = pytz.timezone('Asia/Seoul')` 노출.
- `def parse_date(date_str: str) -> datetime | None` — 현재 `_parse_date` 로직
  그대로. YYYYMMDD, YYYY-MM-DD, YYYY.MM.DD 형식 처리. KST localize.

### 5.4 `pagination.py`

- `def build_page_url(base_url: str, page: int) -> str` — 현재 `fetch_list_items`
  의 페이지네이션 분기 (`fsc.go.kr` → `curPage`, 그 외 → `pageIndex`) 를 함수로
  옮긴다. `re.sub` 정규식 동일.

### 5.5 `list_scraper.py`

- `def fetch_list_items(agency_config: dict, last_crawled_date: datetime | None = None) -> list[dict]`
  — 현재 `ContentScraper.fetch_list_items` 의 로직을 함수로 옮긴다.
  - 동일한 cutoff 정책: `last_crawled - 1day` vs `now - 7days` 중 더 최근 사용.
  - max_pages = 15 동일.
  - `time.sleep(random.uniform(SCRAPER_RETRY_DELAY_MIN, SCRAPER_RETRY_DELAY_MAX))`
    동일 위치.
  - http는 `http.fetch` 사용.
  - 날짜 파싱은 `date_parser.parse_date` 사용.
  - URL 빌드는 `pagination.build_page_url` 사용.
  - 반환 dict 구조 동일 (`title`, `link`, `published_at`, `agency`, `category`).

### 5.6 `content_scraper.py`

- `def fetch_content(url: str, agency_config: dict) -> str | None` — 현재
  `ContentScraper.fetch_content` 로직 그대로. `[Short Content]` 처리, 50자 미만
  태깅, `remove_selectors` 처리 동일.

### 5.7 `sanction_scraper.py`

- `def fetch_sanction_items(agency_config: dict) -> list[dict]` — 현재
  `ContentScraper.fetch_sanction_items` 로직 그대로.
- `def extract_pdf_from_detail(detail_url: str, base_domain: str) -> str | None` —
  현재 `_extract_pdf_from_detail` 로직 그대로.
- `SANCTION_AGENCY_CODES` (phase 2 enum) 사용해 가드.
- 30일 cutoff, max_pages = 10, filter/exclude 키워드 처리 모두 동일.
- 결과 dict 구조 동일 (`title`, `link`, `published_at`, `agency`, `category='sanction_notice'`,
  `pdf_url`).

### 5.8 `scraper.py` facade

- 기존 클래스 인터페이스 보존:

```python
class ContentScraper:
    def fetch_list_items(self, agency_config, last_crawled_date=None):
        return list_scraper.fetch_list_items(agency_config, last_crawled_date)
    def fetch_content(self, url, agency_config):
        return content_scraper.fetch_content(url, agency_config)
    def fetch_sanction_items(self, agency_config):
        return sanction_scraper.fetch_sanction_items(agency_config)
```

- `__init__` 빈 본문(또는 제거). `pipeline.py`가 `ContentScraper()` 를 인스턴스화
  하므로 facade 클래스는 유지한다.

### 5.9 `rss_parser.py` 정리

- 이번 phase에서는 큰 변경 없음. `from config import settings` →
  `from src.config import settings` 한 줄만 정리. 함수 시그니처/동작 그대로.

## Acceptance Criteria

```bash
# 새 모듈 존재
test -f src/collectors/http.py
test -f src/collectors/date_parser.py
test -f src/collectors/pagination.py
test -f src/collectors/list_scraper.py
test -f src/collectors/content_scraper.py
test -f src/collectors/sanction_scraper.py

# facade 클래스 유지
python -c "from src.collectors.scraper import ContentScraper; s=ContentScraper(); assert hasattr(s,'fetch_list_items') and hasattr(s,'fetch_content') and hasattr(s,'fetch_sanction_items')"

# import 사이드 이펙트 0건
python -c "import src.collectors.http; import src.collectors.list_scraper; import src.collectors.sanction_scraper"

# 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline"
```

> 라인 수는 phase 7 `regression-report.md` 에 기록만 하며, phase 5의 hard AC가
> 아니다.

## AC 검증 방법

위 명령 모두 통과 시 phase 5 status를 `"completed"`로.

3회 실패 시 `"error"` + `error_message`.

## 주의사항

- **`agencies.json` selector 구조에 의존하는 dict 접근 키는 절대 바꾸지 마라.**
  (`'list'`, `'title'`, `'date'`, `'link'`, `'content'`, `'pdf_link'`,
  `'filter_keywords'`, `'exclude_keywords'`, `'collection_method'`, `'base_url'`,
  `'category'`)
- cutoff 정책(7일 / 30일), max_pages(15 / 10), `len(rows) < 3` 종료 조건 등 동일.
- random delay 범위와 호출 위치 동일.
- `http.fetch` 도입으로 기존 `requests.get(...)` 직접 호출을 대체할 때, headers/
  timeout/verify 조합이 정확히 동일해야 한다.
- `urllib3.disable_warnings` 가 두 번 호출되지 않게 멱등 보장 (모듈 변수로 상태 보관).
- DB 스키마, `web/`, `agencies.json` diff 0건.
