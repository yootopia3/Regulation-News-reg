# MOEF Source Recovery — Regression Report

날짜: 2026-04-06
선택 경로: **A** (korea.kr `dept_mofe.xml` 슬러그 교체)

> 주의: 본 task의 코드/설정 변경분은 사람이 직접 적용했고, `_runner/run-phases.py`로 실행하지 않았다. 그래서 `tasks/2-moef-source/index.json`과 `tasks/index.json`의 status는 의도적으로 `pending`으로 두었다. 재실행이 필요하면 runner를 그대로 돌릴 수 있다 (phase 문서들은 그 전제로 작성됨).

## 1. 관측 사실 (실측)
- `https://www.korea.kr/rss/dept_moef.xml` (현행, 의심) → 200, 50 entries, 최신 `Tue, 17 Mar 2026 08:25:00 GMT` (≈3주 stale)
- `https://www.korea.kr/rss/dept_mofe.xml` (신규 후보) → 200, 50 entries, 최신 `Mon, 06 Apr 2026 07:18:00 GMT` (당일)
- `https://www.moef.go.kr` → `ConnectionResetError`
- `https://www.mofe.go.kr` → `ConnectionResetError`
- 결정: B는 reachability 실패 → 폐기. A의 freshness가 통과 → A 채택. C 불필요.
- 측정 시 사용한 User-Agent: `Mozilla/5.0`. timeout 10s.

## 2. 구현 변경 (정확히 2개 파일)
- `config/agencies.json` — MOEF `url`을 `dept_moef.xml` → `dept_mofe.xml`로 1줄 교체. 다른 필드/agency 무수정.
- `src/collectors/rss_parser.py` — 동작 무변경 stale 경고 가드:
  - `RSS_STALE_WARN_DAYS = 14`, `logger = logging.getLogger(__name__)` 추가.
  - **수정사항(리뷰 반영):** 이전 버전은 `source_published_at_str` 원문을 RFC822 파서로 다시 파싱해 FSC `%Y-%m-%d %H:%M:%S` fallback 경로를 가드 대상에서 누락했다. 현재 버전은 entries 루프에서 만든 `published_at` datetime을 별도 리스트(`real_dates`)에 그대로 적재해, 파싱에 사용된 그 값과 100% 일관되게 동작한다. `now()`로 대체된 항목은 `real_dates`에 추가하지 않으므로 죽은 소스를 fresh로 오인하지 않는다.

신규 모듈/클래스/파일 없음. 다른 agency/web/db/scripts/.github 변경 없음.

## 3. 검증 결과
| 검증 | 명령 | 결과 |
|---|---|---|
| Import smoke | `source venv/bin/activate && python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer; print('OK')"` | `OK` (비고: bare `python -c ...`은 system Python으로 떨어져 `ModuleNotFoundError: No module named 'feedparser'`로 실패함 — venv 활성화 필수) |
| MOEF targeted fetch | `fetch_rss_feed(MOEF)` 50건, latest age ≤ 7일 | 50건, 최신 `2026-04-06T16:18:00+09:00`, **age 0d** |
| Stale guard — dead URL | `fetch_rss_feed({url:'.../dept_moef.xml'})` | `WARNING:src.collectors.rss_parser:[STALE RSS] MOEF_OLD latest entry is 20d old (2026-03-17); source URL may be dead: https://www.korea.kr/rss/dept_moef.xml` |
| Stale guard — live URL | `fetch_rss_feed({url:'.../dept_mofe.xml'})` | WARNING 미발화 (정상) |
| FSC RSS sanity | `fetch_rss_feed(FSC)` | crash 없음. 0건 (개발 환경에서 fsc.go.kr ConnectionReset — 기존과 동일, 본 task가 도입한 회귀 아님) |
| Scope 가드 (untracked 포함) | `git status --short` | `M config/agencies.json`, `M src/collectors/rss_parser.py`, `M tasks/index.json`, `?? spec/moef-source-round2.md`, `?? tasks/2-moef-source/` 만. `web/`, `db/`, `scripts/`, `.github/`, 다른 agency 없음. |

## 4. 남은 리스크 / 후속
- **Runner readiness (조건부)**: `tasks/2-moef-source/index.json`의 `build_command`와 task/phase metadata는 runner 재실행 가능 상태다 (`phase status == pending`, build_command가 venv 활성화 형태). 다만 phase 1과 phase 3의 live RSS probe는 네트워크/DNS가 동작하는 환경에서만 통과한다. 본 작업이 진행된 일부 sandbox에서는 `www.korea.kr` DNS resolution failure로 직접 재현되지 않았다 — 머지 이전에 정상 네트워크 환경(예: GitHub Actions runner 또는 운영 서버)에서 한 번 돌리는 것이 안전하다.
- **하네스 deviation**: 본 task의 코드/설정 변경분은 runner를 거치지 않고 직접 적용됐다. phase status는 pending이라 runner로 재실행할 수 있고, 재실행 시 phase 2는 already-applied 상태에서 idempotent하게 no-op으로 끝난다 (URL 1줄 교체 + stale guard 둘 다 idempotent).
- **A의 영구성**: 같은 슬러그가 또 abandon될 경우는 새 stale guard가 14일 이내에 경고로 잡는다. 운영에서 WARNING 로그를 봐야 의미가 있으므로 로그 수집 여부는 별도 확인 필요.
- **B 영구 차단 여부**: `mofe.go.kr`는 본 환경에서 두 번 모두 reset됐다. WAF/지역 차단/임시 차단 어느 쪽인지는 본 task에서 단정하지 않는다. 다음 round에서 대체 vantage point로 1회 재시도 가능.
- **DB 실측 결합**: 본 task는 DB insert를 직접 검증하지 않았다. dedup 로직(`Pipeline._is_duplicate`)은 link 키 기반이고 신규 entries의 `link`는 다른 `newsId`를 가지므로 다음 정상 사이클에서 자연 insert될 것이 예상되지만, 실측은 다음 cron 실행 결과로 확인하라.
