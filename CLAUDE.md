# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI 기반 프로젝트 하네스. 두 가지 모드를 지원한다.

- **신규 프로젝트**: `templates/1-초기기획.md` ~ `7-구현시작.md`의 7단계 흐름.
- **기존 코드 리팩토링**: `templates/refactor-start.md` 1장으로 시작 → 곧장 SKILL.md 흐름.

두 모드 모두 phase runner(`_runner/run-phases.py`)가 Claude Code 세션을 순차 실행하여 각 phase를 자동 완료한다.

## Workflow

### 신규 프로젝트
1. **기획 (1~5단계)**: `templates/1-초기기획.md`~`5-기술결정정리.md`를 채워 AI와 대화하며 기획/설계 확정.
2. **문서화 (6단계)**: `templates/6-문서화.md`로 `spec/`에 설계 문서 생성.
3. **구현 (7단계)**: `plan-and-build` skill 사용. 구현 계획을 phase로 분할 → task 파일 생성 → runner로 자동 실행.

### 리팩토링
1. `templates/refactor-start.md`를 채워 목적, 현재 동작, 회귀 체크리스트, 우선순위, AC를 정의.
2. `plan-and-build` skill 흐름으로 진입: `spec/`, 기존 `docs/`, 소스 코드를 함께 읽고 사용자와 논의.
3. 합의 후 `prompts/task-create.md`에 따라 task/phase 파일 생성. `commit_prefix: "refactor"`, `branch_prefix: "refactor"`, `push_on_complete: false` 권장.
4. runner 실행.

## Commands

```bash
# Phase runner 실행
python3 _runner/run-phases.py <task-dir>
# 예: python3 _runner/run-phases.py 0-mvp

# 에러 발생 시: tasks/{task-dir}/index.json에서 해당 phase status를 "pending"으로 변경 후 재실행
python3 _runner/run-phases.py 0-mvp
```

## Task Structure

```
tasks/
  index.json              # 전체 task 목록 (id, name, dir, status)
  {id}-{name}/
    index.json            # phase 목록 + 상태 + build_command + (선택) commit/branch_prefix, push_on_complete
    phase{N}.md           # 각 phase의 자기완결적 구현 지시서
    phase{N}-output.json  # runner가 생성하는 실행 결과 (gitignored)
```

## Phase File Conventions

- 각 `phase{N}.md`는 **독립 Claude 세션이 단독으로 실행**한다. 이전 대화 참조 금지, 필요한 정보를 전부 파일 안에 명시.
- runner는 `phase{N}.md`만 프롬프트에 임베딩한다. 관련 문서(`spec/`, `docs/`, 소스)는 phase 파일 안에 경로로 명시하면 Claude 세션이 직접 읽는다.
- 필수 섹션: 사전 준비(문서/소스 경로 + 이전 phase 산출물), 작업 내용(시그니처 수준 지시), AC(실행 가능한 커맨드), AC 검증 방법, 주의사항.
- scope 최소화: 하나의 phase에서 하나의 레이어/모듈만 다룬다.

## Runner Behavior (`_runner/run-phases.py`)

- `{branch_prefix}-{task-name}` 브랜치를 자동 생성/체크아웃 (`branch_prefix` 기본 `feat`).
- phase마다 `claude -p --dangerously-skip-permissions --output-format json`으로 실행.
- 사전 docs commit은 `tasks/`, `spec/` 중 **존재하는 경로만** 스테이징.
- 2단계 커밋: Claude fallback (`{commit_prefix}(...)`, 기본 `feat`) + runner housekeeping (`chore(...)`).
- `build_command` (index.json에 설정) 실행으로 빌드 검증. 실패 시 error 처리.
- 완료 후 push: `push_on_complete` 플래그로 가드 (기본 `true`). 인증/브랜치 정책 사고 방지를 위해 리팩토링 task에서는 `false` 권장.
- Exit codes: 0=성공, 1=에러, 2=blocked (사용자 개입 필요).
- Phase 타임아웃: 30분.

## Key Rules for Phase Execution

- 기존 동작을 깨지 마라. 리팩토링이라면 동작은 동일하게 유지.
- View/UI에 비즈니스 로직 금지.
- 문자열 리터럴 대신 enum/상수 사용.
- 이전 phase의 네이밍 패턴을 따를 것.
- 중복 코드 금지 — 기존 코드 재사용 또는 공통 유틸 추출.
- 커밋 형식: `{commit_prefix}({task-name}): phase {N} — {phase-name}`

## Git Convention

- `gh_user` 설정 시 GitHub 계정으로 커밋 author 자동 설정 (`_runner/_utils.py`의 `resolve_gh_env`).
- 완료 후 자동 push는 `push_on_complete=true`인 경우에만 `origin/{branch_prefix}-{task-name}`으로 수행.
