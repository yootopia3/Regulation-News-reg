# Phase 3: ssl-opt-in-implementation

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.1 C1, §6 티어 A, §8.1 phase 2, §11 R1, §12 Q3)
- `/home/pacer/projects/reg_brief/spec/round6/ssl-matrix.md` — **이 문서의 `local_*` + `ci_*` 컬럼이 모두 채워져 있고 `final_decision` 이 확정되어 있어야 한다**. 하나라도 `TBD` 가 남아 있으면 phase 3 을 진행할 수 없다 (아래 §1 전제 체크 참조).
- `/home/pacer/projects/reg_brief/spec/backend-architecture.md` (Round 1 에서 확정된 collectors 경계)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/config/settings.py` (`SSL_VERIFY`, `SUPPRESS_SSL_WARNINGS`)
- `/home/pacer/projects/reg_brief/src/collectors/http.py` (공용 `fetch()` 시그니처)
- `/home/pacer/projects/reg_brief/src/collectors/rss_parser.py` (RSS `requests.get` 직접 호출 경로)
- `/home/pacer/projects/reg_brief/src/collectors/scraper.py` / `list_scraper.py` / `content_scraper.py` / `sanction_scraper.py` (`http.fetch` 호출부)
- `/home/pacer/projects/reg_brief/src/config/agency_loader.py` (agency 설정 접근 헬퍼 위치)
- `/home/pacer/projects/reg_brief/config/agencies.json` (opt-out 필드 추가 대상)

이전 phase의 작업물도 확인하라:

- `scripts/ssl_matrix_check.py` (phase 1 산출물)
- `spec/round6/ssl-matrix.md` — phase 1 의 `local_*` 컬럼 + phase 2 의 "CI 실행 절차" 안내 + **사용자가 phase 2 종료 후 수동으로 채워야 했던 `ci_*` 컬럼과 `final_decision`**. phase 2 자체는 cleanly `completed` 으로 끝났지만, 사용자가 워크플로를 실제로 돌리고 결과를 매트릭스에 반영하지 않으면 `ci_*` 가 여전히 `TBD` 인 상태로 phase 3 가 시작될 수 있다 — 이 경우 본 phase §1 의 hard gate 가 즉시 `blocked` 로 잡는다.
- `.github/workflows/ssl-matrix-check.yml` (phase 2 산출물 — Round 6 OOS 의 명시적 예외 1 파일)

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

1. **전제 체크 (hard gate)**: `spec/round6/ssl-matrix.md` 를 파싱하여 모든 agency 행에 대해 `final_decision` 이 `default`, `opt-out`, 또는 `investigate` 중 하나로 확정되어 있는지 확인하라. 하나라도 `TBD` / 빈 값 / 그 외 값이 남아 있으면 **즉시 phase 3 status 를 `blocked`** 으로 바꾸고 `blocked_reason` 에 다음 문구를 기록한 뒤 작업 중단. **임의 추측으로 채우지 마라**:
   > SSL matrix incomplete: <TBD/blank agency 코드 나열>. phase 2 에서 만든 `.github/workflows/ssl-matrix-check.yml` 워크플로를 사용자가 수동 실행하고 (`gh workflow run ssl-matrix-check.yml`), `gh run download` 로 받은 `ssl_matrix_ci.json` 을 `spec/round6/ssl-matrix.md` 의 `ci_*` 컬럼에 붙여 넣은 뒤, 각 agency 의 `final_decision` 을 §결정 기준에 따라 채워야 phase 3 이 진행 가능하다. 사용자 작업이 끝나면 phase 3 의 status 를 `pending` 으로 직접 바꾸고 runner 를 재실행하라.

2. **settings 기본값 전환**: `src/config/settings.py`
   - `SSL_VERIFY = False` → `SSL_VERIFY = True` (module-level constant).
   - 주석 갱신: "Default: verify TLS. Per-agency opt-out via `config/agencies.json` `ssl_verify: false`." 같은 1-2 줄 한국어/영어 주석.
   - `SUPPRESS_SSL_WARNINGS = True` 는 그대로 유지 (opt-out 된 agency 가 여전히 존재할 수 있으므로 urllib3 warning 은 묵음 처리).

3. **agencies.json opt-out 필드 추가**: `config/agencies.json`
   - 매트릭스의 `final_decision == "opt-out"` 인 각 agency 항목에 정확히 `"ssl_verify": false` 필드 추가. **다른 필드는 건드리지 않는다.**
   - `final_decision == "default"` 인 agency 에는 필드를 **추가하지 않는다** (기본값 True 라는 의미).
   - `final_decision == "investigate"` 인 agency 가 있으면 phase 3 을 `blocked` 으로 처리하고 이유에 해당 agency 코드를 남긴다 (설계 미확정).

4. **agency_loader 에 SSL helper 추가**: `src/config/agency_loader.py`
   - 새 함수 `get_ssl_verify(code: str) -> bool` 추가:
     - agency 를 찾아 `ssl_verify` 필드가 명시되어 있으면 그 값을 반환, 없으면 `src.config.settings.SSL_VERIFY` 를 반환.
     - 알 수 없는 code 는 안전 디폴트로 `settings.SSL_VERIFY` 반환 (raise 금지 — 조용히 기본값).
   - `@lru_cache` 는 사용하지 말 것 (settings 가 런타임에 바뀌어도 반영되도록).
   - import 사이드 이펙트 0 유지.

5. **`src/collectors/http.py` 시그니처 확장**:
   - `fetch(url, *, timeout=None)` → `fetch(url, *, timeout=None, verify=None)` 로 파라미터 추가.
   - `verify=None` 이면 현행과 동일하게 `settings.SSL_VERIFY` 사용.
   - `verify` 에 bool 이 오면 그 값을 `requests.get(..., verify=...)` 에 그대로 전달.
   - 기존 호출부 (scraper.py/list/content/sanction) 는 이 phase 안에서 한 번에 전부 업데이트한다 (phase 단위 commit 원칙). agency code 를 알고 있는 시점에서 `get_ssl_verify(code)` 값을 `verify=` 로 넘긴다.
   - agency code 를 모른 채 호출되는 경로가 있으면 (있으면 안 되지만) `verify=None` 으로 두어 현행 동작 유지.

6. **rss_parser.py 경로 통일**:
   - `src/collectors/rss_parser.py` `fetch_rss_feed` 의 `requests.get(target_url, headers=headers, timeout=settings.SCRAPER_TIMEOUT)` 호출에 `verify=get_ssl_verify(agency.get('code') or agency.get('id'))` 를 추가.
   - 이 경로는 현재 `http.fetch` 를 경유하지 않으므로, 필요하면 `from src.config.agency_loader import get_ssl_verify` 만 import 로 추가하고 값을 그대로 전달. `http.fetch` 로의 전환은 이 phase 의 scope 가 아님 (scope 최소화).

7. **collector 호출부 업데이트**: `scraper.py`, `list_scraper.py`, `content_scraper.py`, `sanction_scraper.py` 에서 `http.fetch(url)` 를 호출하는 모든 지점을 찾아:
   - 호출 컨텍스트에서 agency code 가 가용하면 `http.fetch(url, verify=get_ssl_verify(code))` 로 교체.
   - 가용하지 않으면 현행 유지 (fallback: settings 전역값).

8. **테스트 신설**: `tests/unit/collectors/test_http.py` 신설
   - 케이스 A: `fetch(url)` (verify 미지정) → `requests.get` 이 `verify=settings.SSL_VERIFY` 로 호출됨.
   - 케이스 B: `fetch(url, verify=False)` → `verify=False` 가 그대로 전달됨.
   - 케이스 C: `fetch(url, verify=True)` → `verify=True` 가 그대로 전달됨.
   - mock: `src.collectors.http.get_session` 의 session.get 을 `unittest.mock.patch` 로 교체.

9. **테스트 신설**: `tests/unit/config/test_agency_loader_ssl.py` 신설 (또는 기존 `test_agency_loader.py` 에 케이스 추가)
   - 케이스 A: agencies.json fixture (tmp_path 사용) 에 `ssl_verify: false` 가 있는 agency → `get_ssl_verify('X') == False`.
   - 케이스 B: 필드 없는 agency → `settings.SSL_VERIFY` 와 동일.
   - 케이스 C: 알 수 없는 code → `settings.SSL_VERIFY` 와 동일.

## Acceptance Criteria

```bash
# 1) settings 기본값이 True 로 바뀌었는가
grep -q '^SSL_VERIFY = True$' src/config/settings.py

# 2) opt-out agency 에 ssl_verify 필드가 들어갔는가 (최소 1개 이상 — 매트릭스에 따라 달라질 수 있음)
python3 - <<'PY'
import json
with open('config/agencies.json') as f:
    agencies = json.load(f)['agencies']
# 최소 하나 이상의 agency 가 ssl_verify 를 명시하고 있거나, 매트릭스상 모두 default 여야 함.
ssl_fields = [a for a in agencies if 'ssl_verify' in a]
for a in ssl_fields:
    assert isinstance(a['ssl_verify'], bool), f"invalid ssl_verify on {a.get('code')}"
print(f"ssl_verify explicit on {len(ssl_fields)} agencies")
PY

# 3) import smoke
python3 -c "from src.pipeline import Pipeline"
python3 -c "from src.collectors.http import fetch"
python3 -c "from src.config.agency_loader import get_ssl_verify; print(get_ssl_verify('FSS'))"

# 4) 전체 단위 테스트 통과
python3 -m pytest tests/unit -q

# 5) rss_parser 가 여전히 import 가능한가
python3 -c "from src.collectors.rss_parser import fetch_rss_feed, collect_all_rss"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json`의 phase 3 status를 `"completed"`로 변경하라.

§1 의 전제 체크에서 매트릭스가 불완전하면 status 를 `"blocked"` 으로 바꾸고 `blocked_reason` 에 어떤 agency 가 미완성인지 명시하고 즉시 중단하라 — 임의로 채우지 말 것.

일반 AC 실패 시 수정 3회까지 시도하고, 그래도 실패하면 `"error"` + `error_message`.

## 주의사항

- **매트릭스가 불완전하면 추측 금지**. 사용자가 CI workflow 를 수동 실행하고 컬럼을 채운 뒤 phase 3 을 재개해야 한다. 블라인드로 default 를 채우면 운영 사고로 이어질 수 있다.
- `SUPPRESS_SSL_WARNINGS = True` 는 건드리지 말 것. opt-out 된 agency 가 있는 한 urllib3 InsecureRequestWarning 은 여전히 노이즈다.
- `config/agencies.json` 의 다른 필드 (URL, selector, keywords 등) 는 절대 건드리지 마라. opt-out 필드 추가만.
- `http.fetch` 의 기존 호출부를 변경할 때 agency code 를 억지로 끌어오지 마라. 모르는 지점은 기본값으로 그대로 두는 것이 안전.
- 이 phase 는 동작을 의도적으로 바꾸는 phase 다 (기본값 False → True). 일부 agency 에서 실제 SSL 실패가 발생할 수 있음 — 매트릭스가 이를 미리 예측해서 opt-out 에 담았어야 한다. 예측이 빗나가면 수동 롤백이 필요. 그래서 테스트는 mock 기반이고, **실제 1 사이클 수동 검증은 사용자 몫** (task 8 회귀 체크리스트 참조).
- `test_http.py` 는 실제 네트워크 호출 금지. `requests.get` 은 전부 mock.
