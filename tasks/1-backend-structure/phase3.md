# Phase 3: DB Client Lazy Init

`src/db/client.py` 가 import 시점에 환경변수 부재로 raise하는 문제를 없앤다.
`pipeline.py` 가 try/except로 import를 감싸는 방어 코드를 제거한다.

## 사전 준비

설계 의도:

- `spec/refactor-round1.md`
- `spec/backend-architecture.md` (특히 의존성 방향, side effect 제거 계획)

핵심 소스:

- `src/db/client.py` — 현재 import 시 `ValueError` raise
- `src/pipeline.py:46-54` `_init_db` — try/except로 import를 감싸는 코드
- `src/services/analyzer.py` — `from src.db.client import supabase` 사용 여부 확인 (사용 안 함)
- 다른 파일들에서 `from src.db.client import supabase` 사용 위치 grep:

```bash
grep -rn "from src.db.client" src/
grep -rn "from src.db import" src/
```

이전 phase 산출물:

- `spec/backend-architecture.md`
- `src/config/settings.py` (phase 2에서 신설된 `load_env` / `get_supabase_*` getter)

## 작업 내용

### 3.1 `src/db/client.py` lazy 화

기존 코드:

```python
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")
if not url or not key:
    raise ValueError(...)
supabase: Client = create_client(url, key)
```

새 구조:

- 모듈 top-level에서 환경변수 접근 / `create_client` 호출 / raise 전부 제거.
- `def get_supabase_client() -> Client` 함수 제공. 내부에서 `load_env()` 호출
  보장 후 getter 사용해 client 1회 생성, 모듈 변수에 캐싱(singleton).
- 캐시 변수 `_client: Client | None = None`.
- backward compat: `supabase` 라는 모듈 속성은 유지하되, **lazy proxy**로 만든다.
  방법 두 가지 중 하나 선택:
  1. `__getattr__(name)` 모듈 레벨 함수로 `name == "supabase"` 시
     `get_supabase_client()` 반환.
  2. 또는 `supabase = _LazyClient()` 작은 래퍼 클래스로, 메서드 호출 시점에
     `get_supabase_client()` 위임.
  - 어느 쪽이든 `from src.db.client import supabase` 가 작동해야 하고, **import만**
    하는 시점에는 `.env` 가 없어도 raise 되면 안 된다.

### 3.2 `pipeline.py` 정리

이번 라운드의 원칙은 **동작 변경 0건**이다. 따라서 `Pipeline` 의 None fallback
동작을 그대로 보존하면서, import-time raise만 제거한다.

- 클래스 top에서 `from src.db.client import get_supabase_client` 직접 import.
  (이제 import 자체는 안전하다 — 모듈 top-level에서 raise하지 않음.)
- `_init_db` 의 **import** try/except 블록만 제거. 함수 자체는 유지.
- `_init_db` 본문은 `get_supabase_client()` 호출을 try/except로 감싸 실패 시
  `None` 반환 (현재와 동일한 None fallback 동작).
- `self.supabase is None` 인 경우 모든 DB 메서드가 early return 하는 기존 분기
  코드(`_get_last_crawled_date`, `_is_duplicate`, `_save_to_db` 등)는 그대로
  유지한다.

요약: import-time raise는 사라지지만, runtime 에서 supabase 초기화에 실패하면
`Pipeline` 은 여전히 `self.supabase = None` 상태로 동작한다.

### 3.3 다른 호출부

- `from src.db.client import supabase` 사용처를 모두 찾아 그대로 두되, 동작에
  변화가 없는지 확인하라. 기존 객체 인터페이스(`supabase.table(...).select(...)`)
  가 lazy proxy에서도 똑같이 동작해야 한다.

## Acceptance Criteria

```bash
# import 시 raise 없음 (.env 없는 상태에서도)
env -u SUPABASE_URL -u SUPABASE_ANON_KEY python -c "from src.db.client import supabase, get_supabase_client"
env -u SUPABASE_URL -u SUPABASE_ANON_KEY python -c "from src.pipeline import Pipeline"

# pipeline.py에서 try/except import 블록 제거됨
! grep -n "from src.db.client import supabase" src/pipeline.py | grep -i "try\|except"

# 빌드 검증 (import smoke test)
python -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 명령 모두 통과 시 phase 3 status를 `"completed"`로 변경.

3회 실패 시 `"error"` + `error_message`.

## 주의사항

- **이번 라운드는 동작 변경 0건이다.** `Pipeline.__init__`이 `.env` 없을 때
  raise 하도록 바꾸지 마라. `self.supabase = None` 으로 떨어지는 기존 동작을
  그대로 유지하라.
- `_init_db` 함수 자체를 삭제하지 마라. **함수 안의 import try/except만** 제거
  하고, `get_supabase_client()` 호출은 try/except로 감싸 `None` fallback을 유지
  하라.
- supabase-py 의 `Client` 객체 구조를 모르면 옵션 1(`__getattr__`)이 더 안전하다.
- `os.environ` 직접 접근을 새로 추가하지 마라. phase 2에서 만든 getter 사용.
- DB 스키마 / 쿼리 변경 0건.
