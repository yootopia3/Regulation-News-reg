# Phase 6: sanction-rule-derivation

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (§3 — `config/agencies.json` 데이터 변경 금지 규약. 이번 라운드는 "데이터 touch 금지"는 해제되었으나 **값 수정은 여전히 금지**. 파생만 허용)
- `CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. source-first다:

- `config/agencies.json` (9개 agency, `category` 필드 확인)
- `src/config/agency_codes.py` (`SANCTION_AGENCY_CODES` frozenset 정의)
- `src/config/settings.py` (특히 `AGENCIES_JSON_PATH` 상수)
- `src/pipeline.py` (`SANCTION_AGENCY_CODES` 참조 6군데 — 직접 grep으로 확인)

```bash
grep -rn "SANCTION_AGENCY_CODES" src/
```

이전 phase 산출물:

- Phase 3: `tests/unit/**`, `tests/conftest.py`, pytest 구성
- Phase 3: `tests/unit/collectors/test_sanction_scraper.py` (`extract_sanction_key` 테스트)

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **`SANCTION_AGENCY_CODES` 하드코딩 제거 + `agencies.json`의 `category=="sanction_notice"` 파생 + 참조점 교체**만 다룬다. 동작 의미는 변하지 않아야 한다.

### 1. `src/config/agency_loader.py` 신규

```python
"""Runtime-derived agency metadata loader.

Round 2 refactor: `SANCTION_AGENCY_CODES` used to be a hardcoded frozenset
in ``src/config/agency_codes.py``. It is now derived from ``agencies.json``
at load time so that adding a new sanction agency only requires editing
the JSON, not Python source.

Import has no side effects beyond caching. The JSON file is read lazily
on first call.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import FrozenSet, List, Dict

from src.config.settings import AGENCIES_JSON_PATH


@lru_cache(maxsize=1)
def load_agencies() -> List[Dict]:
    with open(AGENCIES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("agencies", []))


@lru_cache(maxsize=1)
def get_sanction_codes() -> FrozenSet[str]:
    """Return the set of agency codes whose category is ``sanction_notice``."""
    return frozenset(
        a["code"]
        for a in load_agencies()
        if a.get("category") == "sanction_notice" and a.get("code")
    )


def is_sanction_agency(code) -> bool:
    """Whether the given agency code represents a sanction-notice source.

    Accepts ``str`` and ``AgencyCode`` (which subclasses ``str``).
    """
    return str(code) in get_sanction_codes()
```

- `AGENCIES_JSON_PATH`는 `src.config.settings`의 기존 상수 재사용.
- `lru_cache(maxsize=1)`로 반복 호출 비용 최소화.
- **순환 import 주의**: `agency_loader`가 `settings`를 import하는 방향만 허용. 반대 방향 금지.

### 2. `src/config/agency_codes.py` 수정

**`SANCTION_AGENCY_CODES` frozenset을 제거**한다. `AgencyCode`, `ArticleCategory` enum 클래스는 그대로 유지.

제거 전:
```python
SANCTION_AGENCY_CODES: frozenset = frozenset(
    {AgencyCode.FSS_SANCTION, AgencyCode.FSS_MGMT_NOTICE}
)
```

제거 후: 해당 블록을 완전히 삭제. `from enum import Enum` 등 나머지는 유지.

### 3. `src/pipeline.py` 수정

`SANCTION_AGENCY_CODES` 참조 6곳을 `is_sanction_agency()` 또는 `get_sanction_codes()`로 교체한다.

교체 원칙:

- **반복 호출 최소화**: `run()` 진입부에서 한 번 `sanction_codes = get_sanction_codes()`를 로컬 변수로 캐시하고 그 변수를 쓰는 방식도 허용. 또는 `is_sanction_agency(code)` 함수 호출.
- **`_is_duplicate`** 내부에서는 `is_sanction_agency(agency_id)`가 가독성 좋음.
- **`_load_sanction_keys`** 내부 루프는 `for agency_code in get_sanction_codes():`로 바꿔도 된다.
- `from src.config.agency_codes import AgencyCode, ArticleCategory, SANCTION_AGENCY_CODES` import 문에서 `SANCTION_AGENCY_CODES`를 제거하고, 필요한 loader 함수를 `from src.config.agency_loader import get_sanction_codes, is_sanction_agency`로 추가.

**기존 동작과 완전히 동일**해야 한다. `agencies.json`에 현재 존재하는 sanction 코드는 `FSS_SANCTION`, `FSS_MGMT_NOTICE` 두 개이며, 이 파생 함수도 정확히 이 두 개를 반환해야 한다.

### 4. 프로젝트 내 다른 참조점 조사·교체

다음 grep으로 모든 참조를 찾아 교체하라:

```bash
grep -rn "SANCTION_AGENCY_CODES" src/ tests/ scripts/
```

`scripts/` 루트 파일은 원래 이번 라운드 scope 밖이지만, 해당 파일이 `SANCTION_AGENCY_CODES`를 import하면 **import 에러만 나지 않게** 최소한의 교체를 수행하라 (로직 변경 금지). 안전하게 수정할 수 없으면 해당 파일은 건드리지 말고, 이 phase에서 `blocked`로 에스컬레이션.

### 5. 테스트 추가

**`tests/unit/config/test_agency_loader.py`** (신규):

- `get_sanction_codes()`가 현재 `agencies.json` 기준 `{"FSS_SANCTION", "FSS_MGMT_NOTICE"}`를 반환.
- `is_sanction_agency("FSS_SANCTION")` → True
- `is_sanction_agency("FSC")` → False
- `is_sanction_agency(AgencyCode.FSS_SANCTION)` → True (enum 입력)
- `load_agencies()`가 9개 agency를 반환 (현재 데이터 기준)

**`tests/unit/pipeline/test_is_duplicate.py`** (신규):

- `Pipeline._is_duplicate`의 sanction 분기가 새 파생 set을 사용해서 올바르게 동작함을 검증한다.
- Supabase 클라이언트는 mock. `Pipeline.__init__`의 초기화 경로를 우회하기 위해 `Pipeline.__new__` 또는 `monkeypatch`로 `supabase`/`scraper`/`analyzer`/`notifier` 속성만 심어주는 fixture 허용.
- **테스트 범위 한정**: `_is_duplicate(item, existing_links, sanction_keys)` 한 메서드만 호출한다.
  - 정상 sanction item (key 추출 성공) → `sanction_keys`에 포함되면 True
  - 정상 sanction item → 미포함이면 False
  - sanction key 추출 실패 시 `existing_links` 폴백 경로
  - non-sanction item → `existing_links`로만 판단
- **이 phase에서 `Pipeline.run()`, `_process_single_item`, `_load_existing_links`, `_fetch_item_content` 등의 통합 시나리오 테스트를 쓰지 마라.** `_is_duplicate` 단일 메서드 단위 테스트만 허용한다. pipeline 통합 테스트는 Round 2 scope 밖이다 (결정 #6).

## Acceptance Criteria

```bash
# 신규 파일
test -f src/config/agency_loader.py
test -f tests/unit/config/test_agency_loader.py
test -f tests/unit/pipeline/test_is_duplicate.py
# 하드코딩 제거 확인
! grep -n "SANCTION_AGENCY_CODES" src/config/agency_codes.py
# 참조 0건 (agency_loader.py 자체와 테스트·주석 제외)
test "$(grep -rn 'SANCTION_AGENCY_CODES' src/ | grep -v 'agency_loader.py' | wc -l)" = "0"
# 파생 결과가 기존과 동일
python3 -c "
from src.config.agency_loader import get_sanction_codes
codes = get_sanction_codes()
assert codes == frozenset({'FSS_SANCTION', 'FSS_MGMT_NOTICE'}), codes
"
# pytest 전체 green (Phase 3 테스트 + Phase 6 신규)
python -m pytest -q
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
# web 회귀 없음
cd web && npm test && npm run build
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 phase 6 status를 `"completed"`로 변경.

`pytest` 실패 시 우선 mock 셋업과 fixture 가정을 의심하라. `src/pipeline.py` 로직 자체는 의미론적으로 동일해야 한다. 만약 기존 동작과 다른 결과가 나온다면 교체 과정에서 버그를 만든 것이다 — 즉시 되돌려라.

3회 이상 실패 시 `"error"` + `error_message`. `scripts/` 루트 파일에서 import 문제로 안전 수정 불가 시 `"blocked"`.

## 주의사항

- **`config/agencies.json` 데이터 수정 금지.** 값도 구조도 건드리지 마라. 읽기만.
- **`AgencyCode`, `ArticleCategory` enum 삭제·수정 금지.** 다른 코드가 import 중.
- **Round 2의 "pipeline 추가 구조 변경" 금지.** `DedupCache`, `CollectorRegistry` 같은 구조 도입을 하지 마라. 이번 phase는 `SANCTION_AGENCY_CODES`를 파생으로 바꾸는 것뿐이다.
- **pipeline 통합 테스트 금지.** `Pipeline.run()`, `_process_single_item` 전체 흐름을 mock으로 구동하는 테스트를 쓰지 마라. `_is_duplicate` 단일 메서드에 한정한다.
- **순환 import 주의.** `src/config/settings.py` → `src/config/agency_loader.py` 방향 금지. 반대(`agency_loader` → `settings`) 방향만 허용.
- **기존 동작 완전 보존.** 현재 `SANCTION_AGENCY_CODES`가 반환하던 값 `{FSS_SANCTION, FSS_MGMT_NOTICE}`와 파생 결과가 정확히 일치해야 한다.
- **`scripts/` 루트 파일 건드리지 마라** (원래 scope 밖). 단 import 에러가 날 경우에 한해 해당 한 줄 import 수정만 허용. 로직 변경 금지.
- **`web/`, `.github/workflows/` 수정 금지.**
- 기존 Phase 3 테스트를 깨지 마라.
- `lru_cache`는 테스트 간 상태가 남을 수 있다. 필요하면 테스트에서 `get_sanction_codes.cache_clear()` 호출.
