# Phase 6: Pipeline Slim

`src/pipeline.py` (236 LOC) 의 `Pipeline` 클래스를 단계별 함수로 분해하고, 사이클
시작 시 dedup 캐시를 1번만 조회하도록 정리한다.

## 사전 준비

설계 의도:

- `spec/refactor-round1.md`
- `spec/backend-architecture.md`

핵심 소스:

- `src/pipeline.py` 전체 (현재 236 LOC)
- `src/main.py`
- 이전 phase 산출물:
  - `src/config/settings.py`, `src/config/agency_codes.py` (phase 2)
  - `src/db/client.py` lazy init (phase 3)
  - `src/services/analyzer/*` (phase 4)
  - `src/collectors/*` (phase 5)

## 작업 내용

### 6.1 책임 분리

`Pipeline` 클래스 안의 메서드들을 다음 그룹으로 나눈다. 클래스를 유지하되, 각
그룹은 작은 helper 함수/메서드로 분리.

1. **수집 단계**: `_collect_rss()`, `_collect_scraper(agency)`,
   `_collect_sanction(agency)`. 각각 list[dict] 반환. 현재 `run()`에 인라인된
   for-loop을 메서드로 추출.
2. **dedup 단계**: `_load_existing_links() -> set[str]` — 사이클 시작 시 1회 호출.
   `articles` 테이블에서 link 컬럼만 select 후 set으로 캐시. `_load_sanction_keys()
   -> set[tuple[str,str,str]]` — `(agency, examMgmtNo, emOpenSeq)` set. 모두
   `__init__` 이 아니라 `run()` 시작 시 호출.
3. **중복 판정**: `_is_duplicate(item, existing_links, sanction_keys) -> bool` —
   기존 두 메서드(`_is_duplicate`, `_is_sanction_duplicate`)를 통합. agency가
   `SANCTION_AGENCY_CODES`에 속하면 sanction_keys로 판정, 아니면 existing_links로.
   **DB 쿼리 0건** (캐시만 사용).
4. **본문 fetch + 분석 + 저장 + 알림**: 기존 `_process_single_item` 을 작은
   helper로 분해:
   - `_fetch_item_content(item, agency_config)`
   - `_analyze_item(item, agency_config)`
   - `_save_item(item)` (기존 `_save_to_db` rename)
   - `_notify_item(item, agency_config)` (현재 `notifier.format_and_send`
     호출부)
5. **`run()`**: 위 단계들을 순서대로 호출하는 ~30 LOC 오케스트레이터. 로그
   메시지 동일 유지.

### 6.2 sanction key 추출 유틸

- `src/collectors/sanction_scraper.py` 또는 새 `src/collectors/sanction_dedup.py`에:
  - `def extract_sanction_key(link: str) -> tuple[str | None, str | None]` —
    `urlparse` + `parse_qs`로 `examMgmtNo`, `emOpenSeq` 추출. 현재 `pipeline.py:
    87-103` 로직과 동일.
- `Pipeline._load_sanction_keys()`는 sanction agency 별로 모든 row의 link를
  가져와 `extract_sanction_key`로 변환하여 set 구성.
- 기존 `pipeline.py` 의 `_is_sanction_duplicate`가 매번 전체 SELECT를 하던 문제는
  사이클당 1회 SELECT로 줄어든다. **DB 스키마 변경 없음.**

### 6.3 last_crawled 캐시

- `_load_last_crawled() -> dict[str, datetime]` — scraper agency 각각에 대해 1회
  SELECT (현재와 동일). 결과를 dict로 캐시. `_collect_scraper`에서 dict 조회만.

### 6.4 enum 활용

- agency 분기는 `AgencyCode` / `SANCTION_AGENCY_CODES` 사용. 문자열 리터럴 0건.

### 6.5 `__init__` 정리

- `agency_map` 로딩, analyzer/notifier/supabase/scraper 인스턴스화는 그대로.
- `try/except`로 None fallback하는 분기는 유지 (운영 안정성).
- DB 캐시는 `__init__`에서 만들지 말고 `run()` 시작 시 만든다 (테스트/재사용성).

## Acceptance Criteria

```bash
# 문자열 리터럴 agency 코드 0건
! grep -E "'(FSC|MOEF|FSS|BOK|FSS_REG|FSC_REG|FSS_REG_INFO|FSS_SANCTION|FSS_MGMT_NOTICE)'" src/pipeline.py

# 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline"

# 사이클 시작 시 dedup 캐시가 호출되는지 (최소: 메서드 존재)
python -c "from src.pipeline import Pipeline; assert hasattr(Pipeline, '_load_existing_links')"
python -c "from src.pipeline import Pipeline; assert hasattr(Pipeline, '_load_sanction_keys')"
```

> `src/pipeline.py` 라인 수는 phase 7 `regression-report.md` 에 기록만 하며,
> phase 6의 hard AC가 아니다.

## AC 검증 방법

위 명령 모두 통과 시 phase 6 status를 `"completed"`로.

3회 실패 시 `"error"` + `error_message`.

## 주의사항

- **DB 스키마 변경 0건.** sanction dedup 효율화는 캐시 SELECT만 사용. 새 컬럼/
  인덱스 추가 금지.
- 현재 `pipeline.py` 의 로그 메시지 (예: `"Starting MarketPulse-Reg Pipeline..."`,
  `"  > Saved to DB."`) 는 그대로 유지. 운영 모니터링 의존.
- `analysis_status == 'ANALYZED'` 인 경우만 알림 — 동일 유지.
- `analyzer.process(...)` 호출 시 인자 순서/키워드 동일.
- `Pipeline.__init__` 시 `.env` 누락에 대한 try/except 패턴은 유지 (phase 3 가이드와 동일).
- 빈 리스트일 때 early return (`if not all_items: ...`) 동일 유지.
- `web/`, `agencies.json`, `.github/`, `scripts/`, 루트 dump 파일 diff 0건.
