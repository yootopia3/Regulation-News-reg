# Backend Architecture — Refactor Round 1 Design

본 문서는 `spec/refactor-round1.md`를 실현하기 위한 모듈 경계 설계다. 코드 변경은
후속 phase에서 수행한다. 이 문서는 사실과 지시만 담는다.

## 1. 현재 구조 한눈에

### 1.1 디렉토리 트리 + 라인 수

```
src/
├── __init__.py
├── main.py                    (21 LOC)   CLI entry. Pipeline 1회 실행 후 종료.
├── pipeline.py                (236 LOC)  수집→중복체크→본문→분석→DB→알림 오케스트레이션.
├── collectors/
│   ├── rss_parser.py          (122 LOC)  RSS feedparser 래퍼 + 모듈 전역 CONFIG_PATH.
│   └── scraper.py             (453 LOC)  HTML 리스트/본문 스크래퍼 + 제재 스크래퍼 + 날짜파서.
├── services/
│   ├── analyzer.py            (361 LOC)  HybridAnalyzer(필터+분석+safeguard) + 프롬프트 문자열.
│   └── notifier.py            (62 LOC)   TelegramNotifier.format_and_send / send_message.
├── db/
│   └── client.py              (13 LOC)   supabase 전역 싱글턴 (import 시 create_client).
└── utils/
    └── logger.py              (73 LOC)   setup_logger + TelegramLoggingHandler.

config/
├── settings.py                (36 LOC)   모델 id, 스크래퍼 타임아웃, 로깅/스케줄 상수.
├── agencies.json                         9개 agency URL/selector/keyword 데이터.
└── safeguard_keywords.json               score 보정용 키워드 룰.
```

### 1.2 파일별 책임 (사실 기반)

- `src/main.py`: `setup_logger()` 호출, `Pipeline(CONFIG_PATH).run()` 호출, 예외 시
  critical 로그 + exit(1).
- `src/pipeline.py`: `Pipeline` 클래스. 내부에서 `HybridAnalyzer`, `TelegramNotifier`,
  `supabase`, `ContentScraper`를 try-import하여 지연 로드. `_get_last_crawled_date`,
  `_is_duplicate`, `_is_sanction_duplicate`(URL 파라미터 `examMgmtNo`/`emOpenSeq` 파싱),
  `_save_to_db`, `run`, `_process_single_item` 포함. 'FSS_SANCTION' / 'FSS_MGMT_NOTICE'
  분기 리터럴이 3회 등장.
- `src/collectors/rss_parser.py`: 모듈 전역 `CONFIG_PATH` 계산 + `load_agencies()`
  (모듈 전역 함수), `parse_date`(RFC 822), `fetch_rss_feed`(method/url 필드 호환),
  `collect_all_rss`. `print()` 로깅 혼재.
- `src/collectors/scraper.py`: `ContentScraper`. `fetch_list_items`(페이지네이션
  `curPage` vs `pageIndex` 분기, `fsc.go.kr` 도메인 리터럴 분기), `fetch_content`(본문
  selector), `_parse_date`(KST 로컬라이즈, `YYYYMMDD` / `YYYY-MM-DD` / `YYYY.MM.DD`),
  `fetch_sanction_items`('FSS_SANCTION'/'FSS_MGMT_NOTICE' 리터럴 분기, `filter_keywords`
  / `exclude_keywords`), `_extract_pdf_from_detail`. 상단 `if settings.SUPPRESS_SSL_WARNINGS`
  블록이 import 시 실행.
- `src/services/analyzer.py`: `HybridAnalyzer`. `__init__`에서 `genai.configure`.
  `_call_api`(Retry+Rate limit), `filter`(Tier1 프롬프트), `analyze`(Tier2 프롬프트),
  `_is_personnel_announcement`(미사용 확인 필요), `_apply_keyword_safeguards`
  (`safeguard_keywords.json` 매번 디스크 로드), `process`. 모듈 최상단에서
  `load_dotenv`, `logging.basicConfig`, `GEMINI_API_KEY = os.getenv(...)` 즉시 실행.
  `RegulationAnalyzer = HybridAnalyzer` alias 존재.
- `src/services/notifier.py`: `TelegramNotifier`. 모듈 최상단 `load_dotenv` +
  env 읽기. `send_message`(`verify=False`), `format_and_send`(risk_level 이모지).
- `src/db/client.py`: 모듈 최상단 `load_dotenv` + env 읽기 + `create_client`. env
  없으면 **import 시점에 ValueError raise**. `supabase` 전역 객체 export.
- `src/utils/logger.py`: `setup_logger`, `TelegramLoggingHandler`(ERROR↑을 텔레그램
  전송). `setup_logger` 내부에서 `TelegramNotifier()` 인스턴스화 → import 시점은
  아니지만 호출 시점에 notifier가 env 의존.
- `config/settings.py`: 모델 id, 스크래퍼/스케줄/로깅 상수. **`.env` 로더 없음**
  (analyzer/notifier/db_client 각자 load_dotenv).
- `config/agencies.json`: 9개 agency 정의. 이번 라운드 변경 금지.
- `config/safeguard_keywords.json`: `high_importance.keywords`,
  `medium_importance.keywords` 스키마. analyzer가 직접 읽음.

## 2. 목표 모듈 경계 (Round 1 종료 시점)

```
src/
├── main.py                    CLI entry (현행 유지).
├── pipeline.py                슬림 오케스트레이터. 수집→중복체크→본문→분석→DB→알림.
├── config/                    ← NEW (src 하위. 기존 루트 config/ 와 공존)
│   ├── __init__.py            재-export 창구.
│   ├── settings.py            상수 + 단일 env 로더 진입점(load_dotenv 1회).
│   └── agency_codes.py        AgencyCode (StrEnum) + 그룹 상수 (SANCTION_CODES).
│   ※ 루트의 config/settings.py, config/agencies.json, config/safeguard_keywords.json
│     은 데이터 파일로 유지. src 코드가 `from config import settings` 하던 기존
│     import 경로는 유지한다. 신규 enum/로더는 본 위치에 둔다.
├── db/
│   └── client.py              lazy init. `get_supabase()` + 모듈 속성 `supabase`.
├── services/
│   ├── analyzer/              ← 기존 analyzer.py 를 패키지로 분해
│   │   ├── __init__.py        `HybridAnalyzer` 슬림 클래스 + `RegulationAnalyzer` alias.
│   │   ├── prompts.py         Tier1 filter 프롬프트 + Tier2 analyze 프롬프트 템플릿 (문자열 상수).
│   │   ├── gemini_client.py   `_call_api` 재시도/rate limit + `genai.configure` lazy.
│   │   ├── safeguards.py      safeguard_keywords.json 로더(1회 캐시) + score 보정 함수.
│   │   └── result_mapper.py   Tier2 응답 JSON → DB 스키마 dict 매핑.
│   └── notifier.py            TelegramNotifier (현행 유지. env lazy 화).
├── collectors/
│   ├── __init__.py            facade: `ContentScraper` 재노출(backward compat).
│   ├── http.py                requests.Session 팩토리 + 공통 headers + SSL 경고 suppress 1회.
│   ├── date_parser.py         `parse_kst_date` (scraper._parse_date + rss_parser.parse_date 통합).
│   ├── list_scraper.py        `fetch_list_items` (페이지네이션 strategy 분리).
│   ├── content_scraper.py     `fetch_content` + `ContentScraper` 파사드 클래스.
│   ├── sanction_scraper.py    `fetch_sanction_items` + `_extract_pdf_from_detail`.
│   └── rss_parser.py          기존 유지. 전역 `load_agencies()`/`CONFIG_PATH` 정리만.
└── utils/
    └── logger.py              (현행 유지).
```

각 파일 단일 책임 (1줄):

- `src/config/settings.py` — 상수 정의 + `load_dotenv` 단일 진입점.
- `src/config/agency_codes.py` — `AgencyCode` enum + 그룹 상수.
- `src/db/client.py` — Supabase 클라이언트 lazy 생성.
- `src/services/analyzer/__init__.py` — HybridAnalyzer 파이프라인 조립.
- `src/services/analyzer/prompts.py` — Gemini 프롬프트 상수.
- `src/services/analyzer/gemini_client.py` — genai.configure + 재시도 호출.
- `src/services/analyzer/safeguards.py` — 키워드 safeguard 룰 로드+적용.
- `src/services/analyzer/result_mapper.py` — Gemini 응답→DB 스키마 변환.
- `src/collectors/http.py` — 공통 HTTP 세션/헤더/SSL 설정.
- `src/collectors/date_parser.py` — KST 날짜 파서 단일화.
- `src/collectors/list_scraper.py` — 리스트 페이지 스크래핑.
- `src/collectors/content_scraper.py` — 본문 스크래핑 + 파사드.
- `src/collectors/sanction_scraper.py` — FSS 제재 전용 스크래퍼.

## 3. 공개 인터페이스 표 (phase 진행 후에도 동일)

후속 phase들이 아래 import 경로와 심볼 시그니처를 **깨뜨리지 않는다**.

| 심볼 | 경로 | 비고 |
| --- | --- | --- |
| `Pipeline` | `src.pipeline.Pipeline` | 클래스 시그니처 `Pipeline(config_path)` 유지. |
| `HybridAnalyzer` | `src.services.analyzer.HybridAnalyzer` | `.process(article, agency_name, category)` 유지. |
| `RegulationAnalyzer` | `src.services.analyzer.RegulationAnalyzer` | backward compat alias. 유지. |
| `TelegramNotifier` | `src.services.notifier.TelegramNotifier` | `.format_and_send`, `.send_message`, `.enabled`. |
| `collect_all_rss` | `src.collectors.rss_parser.collect_all_rss` | 반환 포맷 동일. |
| `ContentScraper` | `src.collectors.scraper.ContentScraper` | facade로 유지. `fetch_list_items`, `fetch_content`, `fetch_sanction_items` 메서드 보존. |
| `supabase` | `src.db.client.supabase` | lazy 객체. import 시 raise 하지 않음. |

※ `from config import settings` 경로도 유지 (기존 루트 config 패키지 import 경로).

## 4. 의존성 방향

```
pipeline ─┬→ services/
          ├→ collectors/
          └→ db/
                      ↓
                    config/   ← src/config + 루트 config 둘 다
                      ↓
                    utils/
```

- 단방향만 허용. 역방향 금지.
- `utils/` 는 최하위. 다른 레이어 import 금지.
- `config/` 는 `utils/`만 의존 가능. `services`, `collectors`, `db`, `pipeline`
  심볼을 import 금지.
- `services/`, `collectors/`, `db/` 끼리의 수평 import 금지. 필요한 데이터는
  `pipeline`이 주입한다.
- `pipeline`은 `main`을 import 금지.

## 5. Agency 코드 Enum 계획

현재 박혀 있는 agency 코드 문자열 리터럴 (`grep -n` 실측):

| 파일:라인 | 리터럴 | 용도 | 치환 후 |
| --- | --- | --- | --- |
| `src/collectors/scraper.py:268` | `FSS_SANCTION and FSS_MGMT_NOTICE` (주석) | docstring | 주석 그대로 유지 (코드 아님). |
| `src/collectors/scraper.py:276` | `['FSS_SANCTION', 'FSS_MGMT_NOTICE']` | 가드 분기 | `if code not in SANCTION_CODES:` |
| `src/pipeline.py:148` | `['FSS_SANCTION', 'FSS_MGMT_NOTICE']` | scraper loop skip | `if agency_id in SANCTION_CODES: continue` |
| `src/pipeline.py:162` | `['FSS_SANCTION', 'FSS_MGMT_NOTICE']` | sanction 대상 필터 | `a.get('code') in SANCTION_CODES` |
| `src/pipeline.py:191` | `['FSS_SANCTION', 'FSS_MGMT_NOTICE']` | dedup 분기 | `if agency_id in SANCTION_CODES:` |
| `src/services/analyzer.py:229` | `'FSS', 'FSC', 'MOEF', 'BOK'` (한글 이름과 함께) | personnel 체크 | `AgencyCode.FSS.value` 등 참조. `_is_personnel_announcement` 자체가 현재 `process`에서 호출되지 않으므로 enum 치환만 하고 호출 여부는 phase 4에서 결정. |

`src/config/agency_codes.py` 신설:

```python
from enum import Enum

class AgencyCode(str, Enum):
    FSC = "FSC"
    MOEF = "MOEF"
    FSS = "FSS"
    BOK = "BOK"
    FSS_REG = "FSS_REG"
    FSC_REG = "FSC_REG"
    FSS_REG_INFO = "FSS_REG_INFO"
    FSS_SANCTION = "FSS_SANCTION"
    FSS_MGMT_NOTICE = "FSS_MGMT_NOTICE"

SANCTION_CODES = frozenset({AgencyCode.FSS_SANCTION.value, AgencyCode.FSS_MGMT_NOTICE.value})
```

`agencies.json` 의 `code` 필드 값은 변경 금지 (round 1 out-of-scope). enum `.value`
로 비교한다.

## 6. Side Effect 제거 계획

`import` 시점에 발생하는 사이드 이펙트 목록:

| 파일:라인 | 현재 side effect | lazy 화 방법 |
| --- | --- | --- |
| `src/collectors/scraper.py:11-15` | `import urllib3` + `urllib3.disable_warnings(...)` 즉시 실행 | `http.py` 내부 1회 호출 함수로 이동. 세션 팩토리 최초 호출 시 한 번만 실행. |
| `src/collectors/rss_parser.py:9` | 모듈 전역 `CONFIG_PATH` 계산 | `load_agencies()` 내부로 이동 or `src/config`에서 import. |
| `src/services/analyzer.py:18` | `load_dotenv(...)` 모듈 import 시 실행 | `src/config/settings.py`에 단일 `load_env()` 함수 두고, `HybridAnalyzer.__init__`에서 호출. |
| `src/services/analyzer.py:21-27` | `from config.settings import MODEL_FILTER_ID ...` | 상수 import는 side effect 아님. 유지. |
| `src/services/analyzer.py:30` | `logging.basicConfig(level=..., format=...)` | 제거. 로깅 설정은 `utils/logger.py` 단일 진입점만 사용. |
| `src/services/analyzer.py:33` | `GEMINI_API_KEY = os.getenv(...)` (모듈 전역) | `gemini_client.py` 내부에서 `__init__` 호출 시 읽음. |
| `src/services/analyzer.py:43` | `genai.configure(api_key=...)` in `__init__` | `gemini_client.py`로 이동. 여전히 생성자에서 호출하되, 모듈 import와 분리. |
| `src/services/notifier.py:5-8` | `load_dotenv` + `TELEGRAM_BOT_TOKEN`/`CHAT_ID` 모듈 전역 읽기 | `__init__` 내부로 이동. |
| `src/db/client.py:5-11` | `load_dotenv` + env 읽기 + **`raise ValueError` at import** + `create_client` | 모듈 최상단에서 전부 제거. `get_supabase()` 지연 함수 + 모듈 속성 `supabase` 를 `__getattr__` 로 구현해 최초 접근 시 생성. env 없으면 최초 접근 시점에만 raise. `pipeline.py:46-54`의 try/except import 가드도 제거 가능. |
| `src/utils/logger.py:4` | `from src.services.notifier import TelegramNotifier` (import 시) | import 자체는 OK (notifier 모듈 import가 lazy 화된 후에는 부작용 없음). 유지. |

추가 가드: `python -c "from src.pipeline import Pipeline"`, `python -c "from
src.services.analyzer import HybridAnalyzer"` 가 `.env` 없이 성공해야 한다
(`refactor-round1.md` §4 회귀 체크리스트).

## 7. 이번 라운드에서 하지 않을 것

`spec/refactor-round1.md` §3 / §8 원문 인용:

> ### 3. 건드리지 않을 범위 (out of scope)
>
> - **DB 스키마**: 이번 라운드에서 변경 0건. 인덱스/nullable 컬럼 추가는 제도상
>   허용 범위로만 남겨두고, 실제 사용은 별도 task(MOEF 또는 성능)에서 한다.
> - **`web/` 프론트엔드**: 전체 제외.
> - **`config/agencies.json`** 의 데이터(URL/selector/keyword): 변경 금지. MOEF 소스
>   교체는 별도 task.
> - **`.github/workflows/*`**: 손대지 않음.
> - **`scripts/debug/`**, 루트 dump 파일(`debug_*.md/.py`, `*.txt`,
>   `agency_stats.json` 등), `docs/*.resolved.*` / 스크린샷: 정리 보류. 삭제·이동
>   금지.
> - **Gemini 프롬프트 본문**: 문장 내용 그대로 옮기기만. 의미 변경 금지.
> - **Telegram 메시지 포맷**: 동일 유지.

> ### 8. 다음 라운드로 미루는 항목
>
> - MOEF 소스 교체 (별도 task).
> - 인덱스/컬럼 추가를 동반한 dedup/성능 개선 (별도 task).
> - 프론트 `DashboardV2.tsx` 분해.
> - `scripts/debug/`, 루트 dump, `docs/*.resolved.*` 정리/아카이브.
