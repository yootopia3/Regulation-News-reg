# Phase 1: ssl-matrix-local

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (특히 §3.1 C1, §6 티어 A, §8.1 phase 1, §11 R1, §12 Q3)
- `/home/pacer/projects/reg_brief/spec/refactor-round1.md` (Round 1 스타일·원칙 참고)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/config/settings.py` (특히 `SSL_VERIFY`, `SUPPRESS_SSL_WARNINGS`, `SCRAPER_TIMEOUT`, `USER_AGENT`)
- `/home/pacer/projects/reg_brief/src/collectors/http.py` (공용 `fetch()` 의 verify 사용처)
- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py` (RSS 경로는 `http.fetch` 를 경유하지 않고 `requests.get` 직접 호출하는지 확인)
- `/home/pacer/projects/reg_brief/src/collectors/scraper.py`, `content_scraper.py`, `list_scraper.py`, `sanction_scraper.py` (실제 사용 URL 추출 경로)
- `/home/pacer/projects/reg_brief/config/agencies.json` (9개 agency 의 URL/`base_url` 필드)

이전 phase의 작업물도 확인하라:

- 본 phase 가 task 8 의 첫 phase 다. 이전 phase 산출물은 없음.

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

본 phase 의 목표는 **코드 변경 0 건**. 오직 SSL 검증 가능성을 조사하고 매트릭스 문서를 만든다.

1. **조사 스크립트 신설**: `scripts/ssl_matrix_check.py` 를 새로 만든다.
   - 입력: `config/agencies.json` 읽기.
   - 각 agency 항목에 대해:
     - `url` 이 RSS (agency `collection_method == 'rss'`) 이면 feed URL 자체를 검사 대상으로 사용.
     - scraper 이면 `url` (list URL) 과 `base_url` 둘 다 검사 대상으로 사용. 둘이 동일하면 1개로 중복 제거.
     - sanction (`collection_method` 이 scraper 이고 카테고리가 sanction) 도 동일.
   - 각 대상 URL 에 대해 **한 번씩만** 다음을 수행:
     - `requests.get(url, verify=True, timeout=20, headers={'User-Agent': ...(settings.USER_AGENT)})`
     - 성공: status_code, elapsed, final URL (redirect 여부) 기록.
     - 실패: exception class 이름 (`requests.exceptions.SSLError`, `ConnectionError`, `Timeout`, `HTTPError`), 메시지 요약 기록.
   - 호출 간 `time.sleep(random.uniform(0.5, 1.0))` 로 소스에 부담 최소화.
   - **fail-soft**: 어떤 대상이 실패해도 스크립트 전체는 완주한다. 끝까지 돌고 결과 테이블을 stdout 에 프린트 + `logs/ssl_matrix_local.json` 파일로 저장 (디렉토리가 없으면 생성).
   - 스크립트는 `if __name__ == '__main__':` 블록 안에서만 실제 HTTP 호출. import 시 부작용 0.
   - 경로: `scripts/ssl_matrix_check.py` (루트 scripts/ 디렉토리 하위. scripts/archive 나 scripts/admin 이 아닌 scripts/ 바로 밑).

2. **로컬 실행**: phase 실행 중인 Claude 세션이 **로컬 환경에서 1회 실행**.
   - 명령: `python3 scripts/ssl_matrix_check.py`
   - 실행 환경: venv 가 활성화되어 있지 않을 수 있으므로 `python3 -c "import requests"` 로 선요건 체크. 없으면 해당 체크만 skip 하고 phase 를 에러로 마킹.
   - 실행 결과 (`logs/ssl_matrix_local.json`) 를 읽어 다음 단계에서 사용.

3. **매트릭스 문서 신설**: `spec/round6/ssl-matrix.md` 를 새로 만든다.
   - 첫 줄: `# SSL Verification Matrix — Round 6 Phase 1/2`
   - 섹션: `## 실행 환경` — 로컬 OS, Python version, requests version, CA bundle 위치 (`python3 -c "import certifi; print(certifi.where())"` 결과), 실행 시각 (ISO 8601 KST), 실행자 (Claude session id 가 있으면 기록).
   - 섹션: `## Agency 매트릭스` — 마크다운 테이블:
     ```
     | agency code | collection_method | target URL | local_ok | local_status | local_error_type | local_error_msg | ci_ok | ci_status | ci_error_type | ci_error_msg | final_decision |
     |---|---|---|---|---|---|---|---|---|---|---|---|
     ```
     - `local_*` 컬럼은 `logs/ssl_matrix_local.json` 에서 채운다.
     - `ci_*` 컬럼은 **전부 `TBD` (phase 2 에서 CI workflow 로 채움)** 으로 남긴다.
     - `final_decision` 은 `TBD` 로 남긴다 (phase 3 시작 시 사용자/다음 session 이 확정).
   - 섹션: `## 결정 기준` — 아래 규칙을 명시:
     - `local_ok=True AND ci_ok=True` → `final_decision = "default"` (verify=True 유지).
     - `local_ok=False OR ci_ok=False` 중 원인이 `SSLError` (cert chain) 이고 양쪽 환경에서 동일하게 발생 → `final_decision = "opt-out"` (이 agency 에 한해 verify=False).
     - `ConnectionError`, `Timeout` 같은 네트워크 사유는 SSL 과 무관 → `final_decision = "default"` (verify=True 유지, 네트워크 문제는 별개로 다룸).
     - 두 환경 결과가 상반되면 (`env_mismatch`) → `final_decision = "investigate"` + 주석에 사유.
   - 섹션: `## 재현 방법` — `python3 scripts/ssl_matrix_check.py` 로 로컬 재현 가능. CI 는 phase 2 에서 추가될 workflow 참고.

4. **주의**: 실제 서비스 코드 (`src/**`, `config/agencies.json`, `.github/**`) 는 이 phase 에서 **절대 수정하지 않는다**. 오직 신규 파일 3 개만 추가:
   - `scripts/ssl_matrix_check.py` (새 파일)
   - `spec/round6/ssl-matrix.md` (새 디렉토리 + 새 파일)
   - `logs/ssl_matrix_local.json` (실행 산출물. `.gitignore` 에 `logs/` 가 이미 있는지 확인 후 처리. 있으면 커밋 대상 아님, 없으면 파일만 남기고 커밋에서 제외해도 됨. 문서에는 스냅샷 내용을 복붙으로 남긴다.)

## Acceptance Criteria

```bash
# 1) 신규 파일이 생성되었는가
test -f scripts/ssl_matrix_check.py
test -f spec/round6/ssl-matrix.md

# 2) 프로덕션 코드는 깨끗한가
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
python3 -m pytest tests/unit -q

# 3) 조사 스크립트가 import smoke 를 통과하는가 (side effect 없음)
python3 -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','scripts/ssl_matrix_check.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('OK')"

# 4) 매트릭스 테이블에 9개 agency 모두 들어 있는가 (code 컬럼 기준)
python3 - <<'PY'
import json, re
with open('config/agencies.json') as f:
    codes = {a['code'] for a in json.load(f)['agencies']}
with open('spec/round6/ssl-matrix.md') as f:
    doc = f.read()
missing = [c for c in codes if c not in doc]
assert not missing, f"ssl-matrix.md missing agencies: {missing}"
print("matrix covers all", len(codes), "agencies")
PY
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 1 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.
작업 중 사용자 개입이 반드시 필요한 상황(예: 네트워크 격리로 인해 조사 자체가 불가능)이 발생하면 status를 `"blocked"`로, `"blocked_reason"` 필드에 사유를 구체적으로 기록하고 작업을 즉시 중단하라.

## 주의사항

- **프로덕션 코드 수정 금지**. `src/**`, `config/agencies.json`, `.github/**`, `web/**` 전부 diff 0. 이 phase 는 조사/문서화만.
- 스크립트에서 실제 네트워크 호출이 실패해도 스크립트 전체가 죽지 않도록 try/except 로 감싸라. 어떤 agency 가 막혀 있는지가 중요한 정보다.
- CI 컬럼은 비워두지 말고 **`TBD`** 로 명시적으로 채워라. 빈 셀은 "검증 안 됨" 과 "검증 필요" 가 구분되지 않는다.
- 매트릭스의 `final_decision` 은 이 phase 에서 확정하지 마라. phase 3 에서 로컬 + CI 결과를 모두 보고 결정한다.
- `scripts/ssl_matrix_check.py` 는 runtime pipeline 이 절대 import 하지 않는 one-shot 도구다. import 시 사이드 이펙트 0 (모든 호출은 `if __name__ == '__main__':` 아래).
- `logs/ssl_matrix_local.json` 은 커밋에서 제외해도 되나, **매트릭스 문서 본문 안에** 실행 시각과 요약 결과를 그대로 남겨라 (gitignored 파일만 남기고 증거가 사라지면 안 된다).
