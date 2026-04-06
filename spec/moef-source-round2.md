# MOEF Source Recovery — Round 2

작성일: 2026-04-06
범위: `MOEF` 1개 agency 한정. 다른 agency · pipeline · DB · web 무수정.

## 목적
- "정상처럼 보이는 죽은 RSS" 상태에 묶인 MOEF 소스를 살아있는 소스로 교체한다.
- 한 사이클에서 MOEF가 stale snapshot이 아닌 실제 최신 보도자료를 읽도록 만든다.

## 입력 (관측 사실)
- 현 설정: `config/agencies.json` MOEF는 RSS, `https://www.korea.kr/rss/dept_moef.xml`.
- 매 사이클 50건 fetch되지만 dedup 후 신규 insert 0건.
- 측정 (2026-04-06 KST):
  - `dept_moef.xml`  → channel updated 2026-03-18, 최신 item 2026-03-17 → **약 3주 stale**
  - `dept_mofe.xml`  → channel updated 2026-04-06, 최신 item 2026-04-06 → **fresh (오늘)**, entries=50
  - `https://www.moef.go.kr` → `ConnectionResetError`
  - `https://www.mofe.go.kr` → `ConnectionResetError`
  - `https://www.moef.go.kr/nw/nes/nesdta.do?menuNo=4010100` → 200, content-length 0 (mofe.go.kr로 redirect되며 빈 응답)
- 부처명 legacy: feed 안에 "재정경제부/재경부" 표기 등장. `moef` (구) → `mofe` (재정경제부) 슬러그 갱신이 누락된 것.

## 옵션 비교
| 옵션 | 내용 | reachability | 유지비 | 결정 |
|---|---|---|---|---|
| **A** | korea.kr의 신규 슬러그(`dept_mofe.xml`)로 교체 | ✅ 200, 오늘자 fresh, 기존 rss_parser와 100% 호환 | 1줄 변경 | **선택** |
| B | mofe.go.kr 직접 HTML scraping (list_scraper 재사용) | ❌ TCP reset / 0-byte body. 운영 환경에서 안정적 fetch 불가 | 새 selector 필요 | 기각 (재현 불가) |
| C | MOEF disable | n/a | - | 기각 (A가 freshness 충족) |

선택 기준:
- 1순위 권고였던 B는 reachability 검증 단계에서 명백히 막힘 → 추측 진행 금지 원칙에 따라 폐기.
- A는 freshness 검증(최신 item이 7일 이내, 실제로는 당일)을 통과하므로 임시방편이 아니라 즉시 회복 가능한 정답.
- 단, A는 같은 stale 재발 위험이 있으므로 최소 가드 1건 동반.

- 결정: A 채택 (`https://www.korea.kr/rss/dept_mofe.xml`). B는 reachability 실패로 기각, C는 freshness 충족으로 불필요.

## 변경 사항 (출력)
1. `config/agencies.json`
   - MOEF의 `url`을 `https://www.korea.kr/rss/dept_moef.xml` → `https://www.korea.kr/rss/dept_mofe.xml`로 교체.
   - 그 외 필드 무수정. 다른 agency 무수정.
2. `src/collectors/rss_parser.py`
   - `fetch_rss_feed` 마지막에, 파싱된 `published_at` 중 최신 값이 `RSS_STALE_WARN_DAYS` (기본 14일) 보다 오래되면 `logger.warning` 1회 출력.
   - 동작 변경 없음 (수집/저장 동작은 동일). MOEF뿐 아니라 RSS 경로 전체에 국소 적용.
3. `tasks/2-moef-source/` 생성 (이 spec과 한 쌍).

## 제약 (Out of scope)
- DB 스키마, web/, db/, scripts/, .github/, 다른 agency 설정, analyzer/pipeline 구조, google.genai 마이그레이션은 건드리지 않는다.
- 새 collector 클래스 신설 금지. 기존 RSS 경로만 사용.

## AC
1. `config/agencies.json` MOEF URL이 `dept_mofe.xml`로 교체되어 있다.
2. 다음 import smoke가 통과한다 (venv 활성화 필수 — bare `python`은 system Python으로 떨어져 `feedparser` 등 의존성 부재로 실패한다).
   - `source venv/bin/activate && python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer; print('OK')"`
3. MOEF targeted verify가 통과한다.
   - `fetch_rss_feed`가 50건 이상 반환하고, 가장 최근 `published_at`이 7일 이내이다.
4. 다른 agency 설정 diff 0, web/db/scripts/.github diff 0.
5. spec(이 파일) + `tasks/2-moef-source/regression-report.md`에 결정과 근거가 1페이지 이내로 남아 있다.
