# Phase 2: backend-source

## 사전 준비

먼저 아래 문서들을 반드시 읽고 프로젝트의 전체 아키텍처와 설계 의도를 이해하라:

- `/home/pacer/projects/reg_brief/CLAUDE.md`
- `/home/pacer/projects/reg_brief/docs/ARCHITECTURE.md`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`
- `/home/pacer/projects/reg_brief/docs/REQUIREMENTS.md`
- `/home/pacer/projects/reg_brief/.cross-review/20260504T040604Z/round_1/author_v2.md`

그리고 이전 phase의 작업물을 반드시 확인하라:

- `/home/pacer/projects/reg_brief/db/migrations/20260504_add_published_at_source.sql`
- `/home/pacer/projects/reg_brief/src/config/agency_codes.py`
- `/home/pacer/projects/reg_brief/docs/SCHEMA.md`

아래 소스와 테스트를 직접 읽고 현재 패턴에 맞춰 작업하라:

- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py`
- `/home/pacer/projects/reg_brief/src/collectors/list_scraper.py`
- `/home/pacer/projects/reg_brief/src/collectors/sanction_scraper.py`
- `/home/pacer/projects/reg_brief/src/pipeline.py`
- `/home/pacer/projects/reg_brief/tests/unit/collectors/test_rss_parser.py`
- `/home/pacer/projects/reg_brief/tests/unit/collectors/test_sanction_scraper.py`
- `/home/pacer/projects/reg_brief/tests/unit/pipeline/test_pdf_url_persist.py`
- `/home/pacer/projects/reg_brief/tests/unit/pipeline/test_run.py`

이전 phase에서 만들어진 데이터 계약을 꼼꼼히 읽고, 새 row에 대해서는 `published_at` fallback 여부와 `published_at_source`가 항상 일치하도록 구현하라.

## 작업 내용

목표: 수집기와 pipeline이 신규 article row에 `published_at_source`를 정확히 채우도록 한다.

1. collector item 생성 경로에 `published_at_source`를 추가한다.
   - `src/collectors/rss_parser.py`
     - RFC 822 또는 FSC `%Y-%m-%d %H:%M:%S` fallback format 파싱 성공: `PublishedAtSource.SOURCE.value`
     - 파싱 실패로 `datetime.now(KST)`를 사용하는 경우: `PublishedAtSource.COLLECTED_FALLBACK.value`
   - `src/collectors/list_scraper.py`
     - `parse_date(date_str)` 성공: `SOURCE`
     - 실패로 `now_kst`를 사용하는 경우: `COLLECTED_FALLBACK`
   - `src/collectors/sanction_scraper.py`
     - `parse_date(date_str)` 성공: `SOURCE`
     - 실패로 `now_kst`를 사용하는 경우: `COLLECTED_FALLBACK`

2. `src/pipeline.py`의 `_save_item()`을 수정한다.
   - insert payload에 `published_at_source`를 포함한다.
   - `item.get('published_at')`가 존재하면 그 값을 그대로 사용한다.
   - `item.get('published_at')`가 없어서 pipeline이 fallback timestamp를 만들 때는 KST-aware timestamp를 사용하고 `published_at_source`를 `COLLECTED_FALLBACK`로 저장한다.
   - item에 `published_at_source`가 없지만 `published_at`은 있으면 legacy-safe하게 `published_at_source`를 `None`으로 저장한다.
   - `pdf_url` merge 로직과 `_notify_item()`에 전달되는 `analysis_result` shape는 바꾸지 않는다.

3. 테스트를 추가하거나 보강한다.
   - RSS 파싱 성공 item은 `published_at_source == "source"`인지 검증한다.
   - RSS 파싱 실패 item은 `published_at_source == "collected_fallback"`인지 검증한다.
   - list scraper 파싱 성공/실패 item을 검증하는 단위 테스트를 추가한다. 네트워크는 `src.collectors.http.fetch`, sleep은 monkeypatch로 막는다.
   - sanction scraper 파싱 성공/실패 item을 검증한다. 네트워크는 monkeypatch하고 PDF 추출은 필요하면 `extract_pdf_from_detail`을 stub 처리한다.
   - pipeline `_save_item()` payload에 `published_at_source`가 포함되는지 검증한다.
   - pipeline fallback path에서 `published_at`이 없을 때 `published_at_source == "collected_fallback"`인지 검증한다.
   - `published_at`은 있지만 `published_at_source`가 없는 legacy-safe item은 insert payload의 `published_at_source is None`인지 검증한다.

## Acceptance Criteria

```bash
# 1) backend source 필드가 주요 경로에 반영됨
grep -q "published_at_source" src/collectors/rss_parser.py
grep -q "published_at_source" src/collectors/list_scraper.py
grep -q "published_at_source" src/collectors/sanction_scraper.py
grep -q "published_at_source" src/pipeline.py

# 2) 새 enum 사용
grep -q "PublishedAtSource" src/collectors/rss_parser.py
grep -q "PublishedAtSource" src/collectors/list_scraper.py
grep -q "PublishedAtSource" src/collectors/sanction_scraper.py
grep -q "PublishedAtSource" src/pipeline.py

# 3) 관련 Python tests
venv/bin/python -m pytest tests/unit/collectors tests/unit/pipeline -q
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/11-mobile-time-display/index.json`의 phase 2 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- 기존 row를 update/backfill하는 코드를 추가하지 마라.
- 날짜 그룹핑/정렬 정책은 frontend phase에서도 그대로 유지된다. backend에서 `published_at` 의미를 재정의하지 마라.
- `datetime.now().isoformat()` 같은 naive fallback을 새로 추가하지 마라. pipeline fallback은 KST-aware여야 한다.
- `analysis_result` 안에 `published_at_source`를 넣지 마라. source는 top-level DB 컬럼이다.
- `published_at`은 있으나 `published_at_source`가 없는 item을 임의로 `source`로 분류하지 마라. 기존/외부 item은 `None`으로 저장한다.
- `pdf_url` merge, sanction duplicate key, RSS retry policy, stale RSS warning 동작을 바꾸지 마라.
