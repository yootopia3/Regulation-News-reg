# Phase 4: pdf-url-persist-in-save

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C2, §7.1, §11 R2, §12 Q1, §12 Q2)
- `/home/pacer/projects/reg_brief/spec/backend-architecture.md` (분석 결과 JSON 키 셋)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/pipeline.py` (특히 `_analyze_item` L236–252, `_save_item` L254–270, `_process_single_item` L335–355)
- `/home/pacer/projects/reg_brief/src/collectors/sanction_scraper.py` (`pdf_url` 생성 경로 — L142–160)
- `/home/pacer/projects/reg_brief/src/services/analyzer/__init__.py` / `hybrid.py` / `result_mapper.py` (analyzer 가 어떤 shape 의 dict 를 반환하는지)
- `/home/pacer/projects/reg_brief/tests/unit/pipeline/test_is_duplicate.py` (기존 pipeline 테스트 스타일 참고)

이전 phase의 작업물도 확인하라:

- Phase 1–3 의 산출물 (SSL 관련). 본 phase 는 SSL 과 독립적이다. 단, phase 3 에서 `_save_item` 을 건드리지 않았는지 확인.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: sanction_scraper 가 만든 `pdf_url` 이 `_save_item` 을 통해 DB 의 `analysis_result` JSON 안에 **반드시** 저장되도록 한다. DB 스키마는 변경 0 건.

1. **`_save_item` 내부 merge 로직 추가**: `src/pipeline.py`
   - 기존 (참고):
     ```python
     def _save_item(self, item: Dict) -> None:
         if not self.supabase:
             return
         try:
             data = {
                 "agency": item['agency'],
                 "title": item['title'],
                 "link": item['link'],
                 "published_at": item.get('published_at') or datetime.now().isoformat(),
                 "content": item.get('content') or "",
                 "analysis_result": item.get('analysis_result'),
                 "category": item.get('category', ArticleCategory.PRESS_RELEASE),
             }
             self.supabase.table("articles").insert(data).execute()
             ...
     ```
   - 수정 목표 (시그니처/바깥 동작 동일, 내부만 변경):
     - `data` 딕셔너리 구성 **직전** 에 아래 merge 단계 실행:
       1. `analysis_result = item.get('analysis_result')`
       2. `pdf_url = item.get('pdf_url')`
       3. `pdf_url` 이 truthy (non-empty string) 이면:
          - `analysis_result` 가 dict 이면 `analysis_result = {**analysis_result, 'pdf_url': pdf_url}` (새 dict 생성, 원본 mutate 금지)
          - `analysis_result` 가 None 이거나 dict 가 아니면 `analysis_result = {'pdf_url': pdf_url}`
     - 그 후 `data['analysis_result'] = analysis_result`.
   - **다른 로직 변경 금지**. Supabase insert 호출, exception 핸들링, 로그 메시지 전부 그대로 유지.
   - 메서드 시그니처 (`def _save_item(self, item: Dict) -> None`) 변경 금지.

2. **_process_single_item 무수정**: 상위 호출부 (`_process_single_item`) 는 건드리지 마라. `item['analysis_result'] = analysis_result` 라인은 그대로 둔다. merge 는 저장 직전에 한 번만.

3. **테스트 신설**: `tests/unit/pipeline/test_pdf_url_persist.py`
   - 구조: fake supabase (mock) 의 `table('articles').insert(...).execute()` 체인을 캡처해 `insert()` 에 전달된 딕셔너리를 검사.
   - Pipeline 생성은 `Pipeline.__init__` 에 supabase 를 직접 주입할 수 없다 (phase 6 에서 DI 가 추가됨). 이 phase 에서는 다음 중 하나를 사용:
     - **권장**: `Pipeline.__new__(Pipeline)` 로 bare instance 를 만들고 필요한 속성 (`self.supabase = fake_supabase`, `self.notifier = None`, `self.analyzer = None`, `self.scraper = None`, `self.agency_map = {}`) 만 직접 설정한 뒤 `_save_item` 을 단독 호출.
     - 또는 `Pipeline` 의 `__init__` 을 `unittest.mock.patch.object` 로 no-op 처리.
   - 케이스:
     - Case A: `item = {'agency': 'FSS_SANCTION', 'title': 't', 'link': 'https://fss.or.kr/...', 'pdf_url': 'https://fss.or.kr/x.pdf', 'analysis_result': {'risk_level': 'HIGH', 'risk_score': 70}}` → 저장된 payload 의 `analysis_result` 에 `pdf_url` 키가 있고 기존 `risk_level`, `risk_score` 도 보존되어야 한다.
     - Case B: 같은 item 에서 `analysis_result=None` → payload 의 `analysis_result == {'pdf_url': 'https://fss.or.kr/x.pdf'}`.
     - Case C: `pdf_url` 이 없는 일반 보도자료 item, `analysis_result={'risk_level':'LOW'}` → payload 의 `analysis_result` 가 변경되지 않음 (`pdf_url` 키 없음).
     - Case D: `pdf_url` 없음 + `analysis_result=None` → payload 의 `analysis_result is None` 그대로.
     - Case E (원본 mutate 금지): Case A 실행 후 원본 `item['analysis_result']` 에 `pdf_url` 키가 **들어가지 않았는지** 확인 (새 dict 를 만들었어야 함).

4. **회귀 체크**: 기존 `tests/unit/pipeline/test_is_duplicate.py` 가 여전히 통과하는지 확인. `_save_item` 변경이 `_is_duplicate` 에 영향을 주지 않아야 한다.

## Acceptance Criteria

```bash
# 1) 신규 테스트 통과
python3 -m pytest tests/unit/pipeline/test_pdf_url_persist.py -q

# 2) 기존 pipeline 테스트 통과
python3 -m pytest tests/unit/pipeline -q

# 3) 전체 단위 테스트 통과
python3 -m pytest tests/unit -q

# 4) import smoke
python3 -c "from src.pipeline import Pipeline"

# 5) _save_item 안에 pdf_url merge 가 들어갔는지 구문 수준 확인
grep -q "pdf_url" src/pipeline.py
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 4 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **DB 스키마 변경 금지**. `pdf_url` 은 `articles.analysis_result` JSON 안에만 저장. Supabase 컬럼 추가 절대 금지.
- **_analyze_item / _process_single_item / _notify_item 수정 금지**. 병합 로직은 `_save_item` 내부에만.
- Telegram 알림 포맷은 변경 금지. `_notify_item` 에 전달되는 `analysis_result` 는 phase 4 이전과 동일한 shape (기존 키 + 선택적 `pdf_url`).
- 원본 `item['analysis_result']` 를 mutate 하지 마라. `{**old, 'pdf_url': ...}` 처럼 새 dict 를 만들어야 한다 (다른 소비자 — 특히 `_notify_item` — 가 mutate 에 의존할 수 있음).
- `analysis_result` 가 dict 가 아닌 이상한 타입 (str, list 등) 으로 들어오는 edge case 는 조용히 `{'pdf_url': pdf_url}` 로 교체. 로그 warning 1 줄.
- 이 phase 는 DI 전이다. 테스트에서 `Pipeline.__init__` 을 우회하는 해킹 (`__new__` 또는 `patch.object`) 을 명시적으로 사용하라 — phase 6 의 DI 가 없는 상태에서 정석 DI 는 불가능하다는 사실을 주석으로 남겨라.
- `Pipeline.__new__(Pipeline)` 패턴은 임시 우회가 아니라 **기존 테스트 컨벤션** 이다. `tests/unit/pipeline/test_is_duplicate.py:23` 의 `pipeline` fixture 가 동일하게 `Pipeline.__new__(Pipeline)` 으로 bare instance 를 만들어 `_is_duplicate` 만 단독 호출한다. 같은 패턴으로 `_save_item` 을 단독 호출하는 것은 컨벤션 준수.
