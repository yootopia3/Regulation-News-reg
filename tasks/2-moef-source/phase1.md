# Phase 1: source-validation-decision

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/moef-source-round2.md` (이번 task의 결정 문서: 옵션 A/B/C 비교, 측정 사실, AC)
- `CLAUDE.md` (하네스 규약, phase 실행 규칙)

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. source-first다:

- `config/agencies.json` (MOEF 항목의 현재 url)
- `src/collectors/rss_parser.py` (`fetch_rss_feed`가 어떤 필드를 어떻게 파싱하는지)
- `src/collectors/list_scraper.py` (B 경로를 택할 경우 재사용할 scraper 진입점)
- `src/collectors/content_scraper.py`
- `src/collectors/pagination.py`
- `src/pipeline.py` (`_collect_rss` / `_collect_scraper` 흐름)

이전 phase 산출물: 없음 (Phase 1).

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

실행 환경에서 다음을 직접 측정하여 옵션 A/B/C 중 어느 경로가 가능한지 결정하라.

1. **A: korea.kr 신규 슬러그 freshness 검증**
   - `https://www.korea.kr/rss/dept_moef.xml` (현행, 의심되는 stale)
   - `https://www.korea.kr/rss/dept_mofe.xml` (재정경제부 슬러그 후보)
   - 각각 HTTP 응답, channel updated, entries[0] pubDate 측정.
   - 신규 후보의 최신 entry pubDate가 **현재 KST 기준 7일 이내**여야 A 채택 가능.
2. **B: 직접 HTML 경로 reachability**
   - `https://www.moef.go.kr` 와 `https://www.mofe.go.kr` 리스트 페이지에 1회 GET.
   - 200 + non-empty body + 안정적인 list/title/date selector를 확보할 수 있어야 B 채택 가능.
3. **결정**
   - B가 reachability+selector 모두 통과하면 → B 채택.
   - 아니면 A의 freshness가 통과하면 → A 채택.
   - 둘 다 실패면 → C (MOEF disable) 채택.
4. 측정 결과와 결정을 `spec/moef-source-round2.md`의 옵션 비교 표 / 결정 섹션에 채워 넣어라. 다른 agency 설정·코드·pipeline 구조는 건드리지 마라.

추측 금지. 모든 결정은 측정값으로 뒷받침되어야 한다.

## Acceptance Criteria

```bash
# 1. spec에 결정 라인 + A/B/C 중 하나의 채택이 명시되어 있는지 확인
grep -E "^- 결정: [ABC] 채택" spec/moef-source-round2.md

# 2. spec에 신·구 RSS 슬러그 관측값이 모두 들어있는지 (기각/채택 근거가 측정 기반인지)
grep -F "dept_moef.xml" spec/moef-source-round2.md
grep -F "dept_mofe.xml" spec/moef-source-round2.md

# 3. 후보 RSS 두 개의 freshness 직접 측정
source venv/bin/activate && python -c "
import requests, feedparser
for u in ['https://www.korea.kr/rss/dept_moef.xml','https://www.korea.kr/rss/dept_mofe.xml']:
    r = requests.get(u, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
    f = feedparser.parse(r.content)
    print(u, r.status_code, len(f.entries), f.entries[0].get('published') if f.entries else None)
"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. spec 문서에 결정(A/B/C)과 근거 측정값이 모두 채워졌고, freshness/reachability 측정 결과가 결정과 일치하면 `tasks/2-moef-source/index.json`의 phase 1 status를 `"completed"`로 변경하라. 측정 자체가 막히면(네트워크/DNS) status를 `"blocked"`로, `"blocked_reason"` 필드에 어떤 호스트에 대해 어떤 오류가 났는지 구체적으로 기록하고 즉시 중단하라. 측정은 됐지만 A/B/C 모두 부적합하다면 `"error"`로 마킹하고 `"error_message"`에 그 이유를 기록하라.

## 주의사항

- 추측 금지. URL 응답·feed updated 모두 실측 후 spec에 기재하라.
- 다른 agency RSS/scraper 설정은 절대 건드리지 마라.
- 이 phase에서는 코드 변경 없음. spec 문서만 갱신한다.
- B를 채택하려면 reachability와 selector 둘 다 확보돼야 한다. 한쪽만 되면 B는 폐기.
