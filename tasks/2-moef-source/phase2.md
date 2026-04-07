# Phase 2: implementation

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/moef-source-round2.md` (Phase 1에서 확정된 결정 — A/B/C 중 무엇)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라:

- `config/agencies.json` (MOEF 항목)
- `src/collectors/rss_parser.py` (`fetch_rss_feed` 흐름, `parse_date` 동작, FSC fallback 경로)
- `src/collectors/list_scraper.py` (B 채택 시 재사용)
- `src/collectors/content_scraper.py` (B 채택 시 재사용)
- `src/pipeline.py` (`_collect_rss` / `_collect_scraper` 분기)

이전 phase 산출물:

- `tasks/2-moef-source/phase1.md`
- `spec/moef-source-round2.md` (Phase 1에서 결정 채워짐)

문서보다 코드가 우선이다.

## 작업 내용

Phase 1에서 확정된 경로에 따라 **최소 변경**으로 구현하라.

### A 채택 시 (korea.kr 신규 슬러그)
1. `config/agencies.json` MOEF 항목의 `url`을 신규 슬러그로 1줄 교체. 다른 필드/agency는 건드리지 마라.
2. (이번 사고 재발 방지) `src/collectors/rss_parser.py`에 stale 경고 가드를 추가하라:
   - 모듈 상수 `RSS_STALE_WARN_DAYS = 14`.
   - `fetch_rss_feed` 내부에서 entries 루프 중 실제로 파싱에 성공한 `published_at` datetime들을 별도로 모은다 (FSC `%Y-%m-%d %H:%M:%S` fallback 경로도 포함). 파싱 실패 후 `now()`로 대체된 항목은 가드 대상에서 제외한다.
   - 함수 마지막에서 그 중 max가 `now() - RSS_STALE_WARN_DAYS`보다 더 오래되면 `logger.warning`을 1회만 출력. 동작(수집/저장)은 변경하지 마라.
   - `logging`을 신규 import하고 `logger = logging.getLogger(__name__)` 정의 1회 추가만 허용.
3. 새 모듈/클래스/파일 신설 금지. `print` 문 신설 금지. 가드는 RSS 경로 안에서만 동작한다.

### B 채택 시 (직접 HTML 스크래핑)
1. `config/agencies.json` MOEF 항목을 RSS → scraper로 전환. `collection_method: "scraper"`, `url`, `base_url`, `selector{list,title,date,link,content}`만 추가.
2. 기존 `list_scraper.fetch_list_items` / `content_scraper.fetch_content` / `pagination.build_page_url` 재사용. 새 collector 클래스 만들지 마라.
3. `pagination.build_page_url`에 mofe.go.kr 분기 추가가 필요하다면 가장 작은 추가만 허용. URL에 페이지네이션 파라미터가 없으면 추가 자체를 포기하라.

### C 채택 시
1. `config/agencies.json` MOEF 항목에 `"enabled": false` 같은 명시적 disable 표시를 두고, RSS 수집기와 pipeline이 이 표시를 존중하도록 가장 작은 분기 1개만 추가하라.
2. disable 사유를 spec 문서와 regression report에 기록하라.

### 모든 경로 공통
- DB 스키마, web/, db/, scripts/, .github/, analyzer/pipeline 구조 변경 금지.
- 다른 agency 설정·selector 변경 금지.
- google.generativeai → google.genai 마이그레이션 금지.

## Acceptance Criteria

```bash
# 1. import smoke
source venv/bin/activate && python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer; print('OK')"

# 2. 변경 scope 가드 (untracked 포함)
git status --short
# 결과에 web/, db/, scripts/, .github/, 다른 agency 행이 등장하면 즉시 실패.
# 허용 경로: config/agencies.json, src/collectors/rss_parser.py(또는 B 시 추가 collector 헬퍼),
#           spec/moef-source-round2.md, tasks/2-moef-source/**

# 3. config/agencies.json diff 가드
#    의도: MOEF url 1줄 교체(= 삭제 1줄 + 추가 1줄)만 허용. 다른 agency 변경 0.
#    `git diff --unified=0 -- config/agencies.json`에서 파일 헤더(`---`,`+++`)를
#    제외한 변경 라인이 정확히 2줄이고, 그 2줄이 옛 슬러그 1줄 삭제 + 새 슬러그 1줄 추가여야 한다.
DIFF=$(git diff --unified=0 -- config/agencies.json | grep -E '^[+-]' | grep -vE '^(---|\+\+\+)')
test "$(printf '%s\n' "$DIFF" | wc -l)" -eq 2 || { echo "FAIL: agency diff has wrong line count"; printf '%s\n' "$DIFF"; exit 1; }
printf '%s\n' "$DIFF" | grep -qF -- '-      "url": "https://www.korea.kr/rss/dept_moef.xml",' || { echo "FAIL: missing old MOEF url removal"; exit 1; }
printf '%s\n' "$DIFF" | grep -qF -- '+      "url": "https://www.korea.kr/rss/dept_mofe.xml",' || { echo "FAIL: missing new MOEF url addition"; exit 1; }
echo "agency diff OK"

# 4. (A 채택 시) MOEF targeted fetch
source venv/bin/activate && python -c "
import json, logging
from datetime import datetime, timezone, timedelta
from dateutil import parser
from src.collectors.rss_parser import fetch_rss_feed
KST = timezone(timedelta(hours=9))
cfg = [a for a in json.load(open('config/agencies.json'))['agencies'] if a['code']=='MOEF'][0]
items = fetch_rss_feed(cfg)
assert len(items) >= 10, f'too few items: {len(items)}'
latest = max(parser.parse(i['published_at']) for i in items)
age = (datetime.now(KST) - latest).days
assert age <= 7, f'still stale: {age}d'
print('MOEF_AC_OK', len(items), latest.isoformat(), 'age', age)
"
```

## AC 검증 방법

위 AC 커맨드를 모두 실행하라. 전부 통과하면 `tasks/2-moef-source/index.json`의 phase 2 status를 `"completed"`로 변경하라. 3회 시도해도 실패하면 `"error"`로 마킹하고 `"error_message"`에 어떤 AC가 어떤 출력으로 실패했는지 기록하라. 네트워크 차단으로 freshness 검증 자체가 막히면 `"blocked"`로, `"blocked_reason"`에 호스트와 오류 종류를 기록하라.

## 주의사항

- `agencies.json`의 trailing comma/형식 실수 금지.
- stale guard는 raw 문자열을 다시 파싱하지 말고 entries 루프에서 만든 `published_at` datetime을 그대로 재사용하라. 그래야 FSC fallback과 일관된다.
- 가드 미발화 조건(`now()` 대체 항목)을 가드 대상에 포함시키지 마라. 모두 `now()`로 대체된 죽은 소스를 fresh로 오인하게 된다.
- B 경로에서 새 helper를 만들 거면 `src/collectors/` 안에 단일 함수 1개 추가 수준으로만 한정. 새 클래스 금지.
