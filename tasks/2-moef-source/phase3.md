# Phase 3: regression-verify

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/moef-source-round2.md`
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라:

- `src/collectors/rss_parser.py` (Phase 2에서 변경됨)
- `config/agencies.json` (Phase 2에서 변경됨)
- `src/pipeline.py` (RSS / scraper 분기 — 변경 없어야 함)

이전 phase 산출물:

- `tasks/2-moef-source/phase1.md`
- `tasks/2-moef-source/phase2.md`
- Phase 2의 코드/설정 변경

문서보다 코드가 우선이다.

## 작업 내용

Phase 2의 변경분이 MOEF 회복에는 성공했고 다른 경로에는 회귀가 없는지 검증하고, 결과를 `tasks/2-moef-source/regression-report.md`에 기록하라.

1. Import smoke 실행.
2. MOEF 신규 소스에서 실제로 fresh entry가 수집되는지 직접 호출로 확인.
3. 다른 RSS agency (FSC) 1회 sanity 호출 — crash 없이 List 반환이면 OK. 0건이어도 회귀 아님 (개발 환경 네트워크 차단 가능). 이전과 동일한 동작을 유지하는지가 기준.
4. Stale guard가 의도대로 동작하는지 확인:
   - 옛 dead URL(`dept_moef.xml`)을 임시로 호출해 `[STALE RSS]` WARNING 1줄이 출력되는지 1회만 검증.
   - 신규 URL에서는 WARNING이 출력되지 않아야 한다.
5. 변경 scope 가드:
   - `git status --short` 결과가 허용 경로(`config/agencies.json`, `src/collectors/rss_parser.py`, `spec/moef-source-round2.md`, `tasks/2-moef-source/**`, `tasks/index.json`) 외 경로를 포함하지 않는지 확인.
   - `git diff --stat` 만 보면 untracked 파일이 누락되므로 반드시 `git status --short`를 같이 본다.
6. 결과를 `regression-report.md`에 기록 (선택 경로 / 관측 사실 / 변경 / 검증 결과 / 남은 리스크).

코드 변경 없음.

## Acceptance Criteria

```bash
# 1. import smoke
source venv/bin/activate && python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer; print('OK')"

# 2. MOEF targeted verify
source venv/bin/activate && python -c "
import json
from datetime import datetime, timezone, timedelta
from dateutil import parser
from src.collectors.rss_parser import fetch_rss_feed
KST = timezone(timedelta(hours=9))
cfg = [a for a in json.load(open('config/agencies.json'))['agencies'] if a['code']=='MOEF'][0]
items = fetch_rss_feed(cfg)
assert len(items) >= 10
age = (datetime.now(KST) - max(parser.parse(i['published_at']) for i in items)).days
assert age <= 7, f'stale: {age}d'
print('MOEF_OK', len(items), 'age', age)
"

# 3. FSC sanity (no crash)
source venv/bin/activate && python -c "
import json
from src.collectors.rss_parser import fetch_rss_feed
cfg = [a for a in json.load(open('config/agencies.json'))['agencies'] if a['code']=='FSC'][0]
items = fetch_rss_feed(cfg)
print('FSC count', len(items))
"

# 4. Stale guard fires on dead URL only
source venv/bin/activate && python -c "
import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(message)s')
from src.collectors.rss_parser import fetch_rss_feed
fetch_rss_feed({'code':'MOEF_OLD','collection_method':'rss','url':'https://www.korea.kr/rss/dept_moef.xml'})
fetch_rss_feed({'code':'MOEF_NEW','collection_method':'rss','url':'https://www.korea.kr/rss/dept_mofe.xml'})
"
# 기대: 첫 번째 호출에서 [STALE RSS] WARNING 1줄, 두 번째에서는 없음.

# 5. Scope 가드 (untracked 포함)
git status --short
# 허용 경로 밖이면 실패.
```

## AC 검증 방법

위 AC 커맨드를 모두 실행하고 출력을 `regression-report.md`에 그대로 기록하라. 모두 통과하면 `tasks/2-moef-source/index.json`의 phase 3 status를 `"completed"`로 변경하라. 실패하면 `"error"`로 마킹하고 어떤 AC가 어떻게 실패했는지 `"error_message"`에 기록하라. 네트워크 차단으로 freshness/sanity 측정이 막히면 `"blocked"`로, `"blocked_reason"`에 막힌 호스트와 오류 종류를 기록하라.

## 주의사항

- 이 phase에서는 기능 코드를 추가로 수정하지 마라. 측정과 보고만 한다.
- `git diff --stat` 단독으로 scope를 판단하지 마라. 그건 untracked 파일을 누락한다.
- regression-report는 과장 없이 측정값 그대로만 기록하라.
