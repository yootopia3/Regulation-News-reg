# Phase 2: ssl-matrix-ci-workflow

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§4 OOS 의 workflow 예외, §8.1 phase 2, §11 R1, §12 Q3)
- `/home/pacer/projects/reg_brief/spec/round6/ssl-matrix.md` (phase 1 에서 생성된 로컬 매트릭스)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라:

- `/home/pacer/projects/reg_brief/scripts/ssl_matrix_check.py` (phase 1 산출물. 이걸 CI 에서도 동일하게 실행한다)
- `/home/pacer/projects/reg_brief/.github/workflows/` 디렉토리의 **기존** workflow 파일들 — 이름/권한/runner 스타일을 확인해서 새 workflow 도 같은 컨벤션을 따르도록 한다.
- `/home/pacer/projects/reg_brief/requirements.txt` (CI 에서 어떤 패키지가 필요한지 확인; `requests` 는 아마 이미 들어 있음)

이전 phase의 작업물도 확인하라:

- `scripts/ssl_matrix_check.py` (phase 1)
- `spec/round6/ssl-matrix.md` (phase 1)

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

본 phase 의 목표는 **CI 환경에서 동일한 SSL 조사가 재현 가능한 workflow 파일을 추가** 하는 것. 실제 CI 실행은 사용자가 phase 2 종료 후 수동으로 한다. phase 2 자체는 파일만 준비하고 정상 `completed` 으로 끝낸다. CI 결과 수집 → 매트릭스 반영 → `final_decision` 확정은 사용자 수동 작업이며, 이를 마치지 못한 상태로 phase 3 가 시작되면 phase 3 의 hard gate 가 즉시 `blocked` 로 잡는다.

> Roadmap §4 OOS 메모: `.github/workflows/*` 는 기본 OOS 지만, 본 phase 의 `ssl-matrix-check.yml` **1 파일** 은 명시적 예외다. 이 1 파일 외에는 기존 workflow 를 1 byte 도 건드리지 마라.

1. **GH Actions workflow 신설**: `.github/workflows/ssl-matrix-check.yml`
   - Trigger: **`workflow_dispatch` 만**. schedule / push / pull_request 자동 트리거 절대 금지.
   - runs-on: `ubuntu-latest`
   - 권한: `permissions: contents: read` 만. write 권한 금지.
   - Steps:
     1. `actions/checkout@v5`
     2. `actions/setup-python@v6` (python-version: **`'3.10'`** — `.github/workflows/ci.yml` 과 `news_collector_v2_active.yml` 의 기존 값과 동일하게 맞춘다. 다른 버전으로 가지 마라.)
     3. `pip install -r requirements.txt` (스크립트가 의존하는 `requests`, `python-dotenv` 등 확보)
     4. `python3 scripts/ssl_matrix_check.py` — 로컬과 동일 스크립트 실행. 출력 경로 환경변수 `SSL_MATRIX_OUTPUT=artifacts/ssl_matrix_ci.json` 같이 override 가능하도록 phase 1 스크립트가 처리했다면 그 경로를 사용. 안 했다면 기본 `logs/ssl_matrix_local.json` 을 그대로 업로드.
     5. `actions/upload-artifact@v4` 로 json 산출물을 `ssl-matrix-ci-result` artifact 로 업로드. retention-days: 14.
   - env / secrets 참조 금지. API key / supabase key 주입 금지.
   - name: `SSL Matrix Check (Round 6 Phase 2)`

2. **매트릭스 문서 갱신**: `spec/round6/ssl-matrix.md` 의 끝에 새 섹션 추가:
   - `## CI 실행 절차` 섹션:
     - workflow 수동 실행 명령 예시:
       ```
       gh workflow run ssl-matrix-check.yml
       gh run watch                    # 실행 감시
       gh run download --name ssl-matrix-ci-result --dir ./.ssl-matrix-ci-tmp
       ```
     - artifact 에서 `ssl_matrix_ci.json` 을 꺼내 `spec/round6/ssl-matrix.md` 의 `ci_*` 컬럼에 붙여 넣는 방법을 1 단락으로 설명.
     - CI 실행자가 사용자임을 명시: "phase 2 의 Claude 세션은 이 workflow 를 실행하지 않는다. phase 2 는 워크플로 파일과 안내 문서만 만들고 정상 종료한다. 사용자가 수동으로 한 번 돌려 결과를 `ci_*` 컬럼과 `final_decision` 에 채워야 phase 3 이 진행 가능하다 (phase 3 hard gate)."
   - 기존 `local_*` 컬럼은 그대로 보존. `ci_*` 컬럼은 phase 1 에서 `TBD` 로 들어가 있어야 한다 (아직 사용자 수동 실행 전).

## Acceptance Criteria

```bash
# 1) 새 workflow 파일 존재 + 최소 형상 확인
test -f .github/workflows/ssl-matrix-check.yml
grep -q "workflow_dispatch" .github/workflows/ssl-matrix-check.yml
grep -q "upload-artifact" .github/workflows/ssl-matrix-check.yml
! grep -q "schedule:" .github/workflows/ssl-matrix-check.yml
! grep -q "secrets\." .github/workflows/ssl-matrix-check.yml

# 2) 매트릭스 문서에 CI 실행 절차 섹션이 들어갔는가
grep -q "CI 실행 절차" spec/round6/ssl-matrix.md
grep -q "gh workflow run ssl-matrix-check.yml" spec/round6/ssl-matrix.md

# 3) 프로덕션 코드는 여전히 깨끗한가
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
python3 -m pytest tests/unit -q

# 4) 기존 workflow 들이 깨지지 않았는가 (yaml 파싱)
python3 - <<'PY'
import pathlib, sys
try:
    import yaml
except Exception:
    sys.exit(0)  # yaml 모듈 없으면 skip
for p in pathlib.Path('.github/workflows').glob('*.yml'):
    yaml.safe_load(p.read_text())
print("all workflows parse")
PY
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/8-round6-backend-safety/index.json` 의 phase 2 status 를 `"completed"` 로 변경하라.

CI 워크플로의 **실제 실행** 은 사용자 수동 작업이며 phase 2 의 책임이 아니다. phase 2 는 워크플로 파일 + 매트릭스 안내 문서가 cleanly 작성된 시점에서 종료한다. 매트릭스의 `ci_*` 컬럼이 빈 채로 phase 3 에 진입하면 phase 3 의 hard gate (그 phase 의 §1 참조) 가 즉시 `blocked` 로 잡으므로, 본 phase 가 self-block 을 시도할 필요는 없다.

수정 3회 이상 시도해도 AC 가 실패하면 status 를 `"error"` 로 변경하고, 에러 내용을 index.json 의 해당 phase 에 `"error_message"` 필드로 기록하라.

## 주의사항

- **프로덕션 코드 수정 금지**. `src/**`, `config/agencies.json`, `web/**` 전부 diff 0.
- **기존 workflow 파일 수정 금지**. `ssl-matrix-check.yml` **신규 1 파일만** 추가. roadmap §4 OOS 의 명시적 예외는 이 1 파일에 한정된다.
- workflow 의 trigger 는 **반드시 `workflow_dispatch` 만**. schedule 나 push 자동 트리거를 붙이면 예상치 못한 CI 비용 + 요금청구 리스크가 생긴다.
- secrets / env.SUPABASE_* / env.GEMINI_API_KEY 등 일체 참조 금지. 이 workflow 는 SSL 인증서 체인 조사만 한다.
- CI 에서 `scripts/ssl_matrix_check.py` 를 돌릴 때 `venv/bin/python` 이 아닌 `python3` 를 쓴다 (GH runner 의 python 이 그대로 쓰임).
- `actions/checkout@v5`, `actions/setup-python@v6`, `actions/upload-artifact@v4` 사용 — 기존 workflow 들의 버전과 통일.
- python-version 은 반드시 `'3.10'`. 기존 `ci.yml` 과 `news_collector_v2_active.yml` 모두 3.10 으로 고정되어 있다.
- phase 2 자체는 self-block 하지 않는다. CI 결과 누락의 차단 책임은 phase 3 의 hard gate 로 일원화되어 있다.
