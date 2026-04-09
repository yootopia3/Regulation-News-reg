# Phase 7: pipeline-run-test

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C4, §8.1 phase 5)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/pipeline.py` (phase 6 에서 DI 가 추가된 상태. `__init__`, `run`, `_process_single_item`, `_is_duplicate`, `_save_item`, `_notify_item` 전부.)
- `/home/pacer/projects/reg_brief/src/collectors/sanction_scraper.py` (item dict shape: `title`, `link`, `published_at`, `agency`, `category`, `pdf_url`)
- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py` (RSS item shape: `agency`, `title`, `link`, `published_at`, `source_published_at_str`)
- `/home/pacer/projects/reg_brief/tests/unit/pipeline/test_is_duplicate.py` (기존 테스트 스타일 참고)
- `/home/pacer/projects/reg_brief/config/agencies.json` (Pipeline 이 `_load_agency_map` 에서 읽는 구조 확인)

이전 phase의 작업물도 확인하라:

- Phase 4 의 `_save_item` pdf_url merge 로직.
- Phase 6 의 DI 시그니처.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: phase 6 의 DI 를 사용해 `Pipeline.run()` 의 end-to-end 흐름을 단위 테스트로 커버한다. 실제 네트워크 / DB / Gemini 호출 없이.

1. **Fake 의존성 구현**: `tests/unit/pipeline/test_run.py` 안에 로컬 fake 들을 정의 (별도 모듈로 빼지 말 것 — 테스트 파일 하나로 완결).

   - **FakeAnalyzer**: `process(self, article, agency_name, category) -> dict` 만 구현. 호출 카운터 유지. 사전 주입된 리턴 값 (dict or None) 을 반환.

   - **FakeNotifier**: `enabled = True` 속성, `format_and_send(a_name, title, link, analysis_result)` 메서드. 호출 인자를 리스트로 축적.

   - **FakeScraper**: `fetch_list_items(self, agency, last_crawled_date=None) -> list` / `fetch_content(self, link, agency_config) -> str` / `fetch_sanction_items(self, agency) -> list` 세 개. 사전 주입된 반환 값 매핑을 사용.

   - **FakeSupabase**: Supabase client chain 을 간략히 흉내. `self.inserted = []`, `self.selected_links = set()` 등 내부 상태. 반드시 지원할 chain:
     - `table(name).select(cols).range(s,e).execute()` → `.data` 에 pre-seeded links 를 반환.
     - `table(name).select(cols).eq('agency', code).range(s,e).execute()` → sanction key 용.
     - `table(name).select(cols).eq('agency', code).order(...).limit(1).execute()` → last_crawled 용.
     - `table(name).insert(data).execute()` → `self.inserted.append(data)`.
   - 체이닝을 위해 반환 객체는 `_Chain` 같은 내부 클래스 사용 권장.

2. **테스트 케이스** — 모두 `tests/unit/pipeline/test_run.py` 안:

   **T1. 단일 신규 RSS item 처리**:
   - Pre-seeded supabase links: `set()` (비어 있음).
   - FakeAnalyzer 리턴: `{'risk_level': 'LOW', 'risk_score': 10, 'analysis_status': 'ANALYZED'}`.
   - FakeScraper `fetch_list_items` 는 빈 리스트, `fetch_sanction_items` 빈 리스트.
   - RSS 는 monkeypatch 로 `src.pipeline.collect_all_rss` 를 `lambda: [<1개 신규 item>]` 으로 교체.
   - Pipeline 생성: `Pipeline('config/agencies.json', analyzer=fake_analyzer, notifier=fake_notifier, db=fake_db, scraper=fake_scraper)`.
   - `pipeline.run()` 실행.
   - 어설션: fake_db.inserted 에 1건. fake_notifier 호출 1회. fake_analyzer.process 호출 1회.

   **T2. 중복 item**:
   - Pre-seeded supabase links 에 해당 item 의 `link` 포함.
   - 같은 item 을 RSS 로 주입.
   - `pipeline.run()` 실행 후 fake_db.inserted 에 0건. fake_notifier 호출 0회. fake_analyzer 호출 0회.

   **T3. analyzer None 반환**:
   - FakeAnalyzer 가 `process` 에서 `None` 반환.
   - fake_db.inserted 에 1건은 들어가되 `analysis_result` 는 None.
   - fake_notifier 호출 0회 (None 이면 notify 안 함).

   **T4. sanction item + pdf_url preserve (phase 4 회귀 체크)**:
   - FakeScraper `fetch_sanction_items` 가 `[{'title':'t','link':'https://fss.or.kr/sanction?examMgmtNo=A&emOpenSeq=1','published_at':'2026-04-08T00:00:00+0900','agency':'FSS_SANCTION','category':'sanction_notice','pdf_url':'https://fss.or.kr/x.pdf'}]` 반환.
   - FakeAnalyzer 는 `{'risk_level':'HIGH','risk_score':80,'analysis_status':'ANALYZED'}` 반환.
   - RSS / 일반 scraper 는 빈 리스트.
   - `pipeline.run()` 실행.
   - 어설션: fake_db.inserted[0]['analysis_result'] 에 `'pdf_url'` 키가 존재하고 `'risk_level'` 도 보존되어 있다.

   **T5. sanction duplicate 체크**:
   - Pre-seeded sanction_keys 에 `('FSS_SANCTION','A','1')` 가 있는 상태.
   - 같은 identity 의 새 item 을 scraper 가 반환.
   - `pipeline.run()` 실행 후 fake_db.inserted 에 0건.

3. **monkeypatch 사용 지침**:
   - `src.pipeline.collect_all_rss` 는 함수 참조 — `monkeypatch.setattr('src.pipeline.collect_all_rss', fake_rss)` 로 치환.
   - `src.collectors.sanction_scraper.extract_sanction_key` 가 sanction T5 에서 올바르게 `('A','1')` 반환하는지 확인. 필요하면 별도 monkeypatch.
   - 실제 `requests` / `supabase-py` / `google.genai` import 는 발생해도 되지만 **호출되면 안 된다**. fake 가 차단.

4. **config 로딩**:
   - `Pipeline('config/agencies.json', ...)` 호출 시 실제 `config/agencies.json` 을 읽는다. 이 파일은 저장소에 있으므로 테스트에서 그대로 사용 가능. 별도 fixture 파일 만들지 말 것.

## Acceptance Criteria

```bash
# 1) 신규 테스트 파일 생성
test -f tests/unit/pipeline/test_run.py

# 2) 최소 5개 테스트 케이스 (T1–T5)
python3 -m pytest tests/unit/pipeline/test_run.py -v -q 2>&1 | grep -E "PASSED|FAILED" | wc -l | awk '{if ($1 < 5) exit 1}'

# 3) 신규 테스트 통과
python3 -m pytest tests/unit/pipeline/test_run.py -q

# 4) 기존 pipeline 테스트 무회귀
python3 -m pytest tests/unit/pipeline -q

# 5) 전체 단위 테스트 무회귀
python3 -m pytest tests/unit -q

# 6) 실제 네트워크 호출을 하지 않는지 스모크 (이 체크는 대략적) — requests.get 이 patch 없이 호출되면 실패하도록 테스트 파일 안에서 `raise` 를 거는 pytest-socket 같은 트릭은 선택사항.
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 7 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **production 코드 수정 금지**. `src/**` 를 건드리지 마라. 이 phase 는 오직 `tests/unit/pipeline/test_run.py` 1 파일 추가.
- 실제 네트워크 호출 / 실제 supabase 호출 / 실제 Gemini 호출 **절대 금지**. 실패 시 테스트가 환경에 의존하게 된다.
- `Pipeline.__init__` 의 `_load_agency_map` 은 실제 `config/agencies.json` 을 읽지만, 이건 저장소 파일이라 환경 의존이 아니다. 읽기 실패는 `_load_agency_map` 내부 try/except 로 이미 방어되어 있다.
- FakeSupabase 의 chain 구현은 **최소한**만 — 실제 필요한 경로만 흉내 낸다. 전체 supabase-py 인터페이스를 구현하지 마라.
- T4 의 pdf_url 어설션은 phase 4 에 대한 회귀 테스트 성격이다. 실패하면 phase 4 의 merge 로직이 망가진 것.
- `pipeline.run()` 은 logger.info 를 많이 부른다. 로그 출력이 pytest 노이즈가 되면 `caplog` 를 쓰거나 `--log-cli-level=WARNING` 으로 테스트 실행.
- `Pipeline` 이 `self.agency_map` 을 dict 로 로드하는 사실을 이용해 FakeScraper 는 특정 agency code 에만 데이터를 돌려주도록 작성. 모든 agency 에 같은 데이터를 돌려주면 중복으로 처리된다.
