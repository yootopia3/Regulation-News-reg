# Phase 2: secret-tooling

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `spec/refactor-round1.md` (§2 "현재 동작" — 환경변수 인터페이스 목록)
- `CLAUDE.md`
- Phase 1 산출물: `.env.example`, `web/.env.local.example`, `.gitignore`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. source-first다:

- `src/config/settings.py` (env 키: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- `web/middleware.ts` (세션 쿠키 이름: `mp_session`)
- `web/lib/auth.ts` (존재하면)
- `web/app/api/auth/login/route.ts` (존재하면, `APP_PASSCODE`/`SESSION_SECRET` 사용처)
- `.github/workflows/news_collector.yml`, `news_collector_v2_active.yml`, `watchdog.yml` (기존 워크플로 — 이번 phase는 손대지 않음)

이전 phase 산출물:

- `.env.example` (루트, placeholder만)
- `web/.env.local.example` (placeholder만)

문서보다 코드가 우선이다.

## 작업 내용

이 phase는 **secret scan 도구 + rotation checklist 문서화**만 다룬다. 다음 사항은 이 phase의 범위가 아니다:

- **실제 키 rotate는 사용자가 수동으로 수행한다.** Supabase/Vercel/GitHub Actions에 로그인해야 하므로 phase runner가 할 수 없다. 이 phase는 체크리스트만 제공한다.
- **`.env.example`, `web/.env.local.example`은 Phase 1 산출물**이다. Phase 2에서 다시 만들지 마라. `.gitleaks.toml`의 allowlist에서 참조만 한다.
- **git history 재작성(`git filter-repo`) 금지.** rotate-only 전략이다.

### 1. `.pre-commit-config.yaml` 신규

최소 구성. gitleaks hook 하나만.

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

### 2. `.gitleaks.toml` 신규

기본 룰셋을 상속하고, Phase 1에서 만든 example 파일을 allowlist에 추가한다.

```toml
[extend]
useDefault = true

[allowlist]
description = "Allow placeholder values in example env files"
paths = [
    '''^\.env\.example$''',
    '''^web/\.env\.local\.example$''',
    '''^docs/secret-rotation-checklist\.md$''',
]
```

### 3. `.github/workflows/ci.yml` 신규

**이 파일은 Phase 2에서 처음 만든다.** Phase 3(python-test)과 Phase 4(web-test)가 이 파일에 job을 추가할 예정이다. 이 phase에서는 `gitleaks` job 1개만 등록한다. stub job을 미리 넣지 마라.

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}
```

`GITLEAKS_LICENSE` 시크릿이 repo에 없어도 action은 오픈소스 모드로 동작하므로 문제 없음.

### 4. `docs/secret-rotation-checklist.md` 신규

사용자가 수동 수행할 rotate 체크리스트. 실제 키 조각·해시·JWT를 기록하지 마라. 커밋 해시와 절차만.

```markdown
# Secret Rotation Checklist (Round 2)

`web/.env.local`이 커밋 `89c8750` (2026-04-07, phase 1 — backend-hygiene)에서
추가되고 커밋 `5b029d3` (2026-04-07, chore(secrets): stop tracking web/.env.local)에서
삭제되었다. 약 20분간 tracked 상태였고, 해당 내용은 git history에 영구 잔존한다.
Round 2는 rotate-only 전략이므로 `git filter-repo`는 수행하지 않는다.

## Rotate 대상

- [ ] `APP_PASSCODE` — 새 값 생성, Vercel env 업데이트
- [ ] `SESSION_SECRET` — `openssl rand -hex 32`로 재생성, Vercel env 업데이트
- [ ] Supabase anon JWT — Supabase Dashboard → Project Settings → API → Roll anon key
- [ ] Supabase service_role JWT — 동일 경로에서 Roll service_role key
- [ ] (예방적) `GEMINI_API_KEY` — Google AI Studio에서 재발급
- [ ] (예방적) `TELEGRAM_BOT_TOKEN` — BotFather에서 재발급

## 반영할 저장소

- [ ] Vercel project env (production + preview + development)
- [ ] GitHub Actions repository secrets (`news_collector_v2_active.yml`이 사용하는 키)
- [ ] 로컬 `.env`, `web/.env.local` (커밋 금지)

## 완료 확인

- [ ] `gitleaks detect --no-banner --redact` 워킹트리 스캔 clean
- [ ] Vercel 배포 후 `/login` → `/` → `/api/report` 정상 동작
- [ ] GitHub Actions `news_collector_v2_active.yml` 수동 트리거 후 성공
```

### 5. README 또는 `CLAUDE.md`에 셋업 한 줄 (선택, skip 허용)

`CLAUDE.md`는 사용자 소유이므로 수정 금지. `README.md`가 존재하고 셋업 섹션이 있다면 아래 한 줄만 append:

```
로컬 셋업: `cp .env.example .env && cp web/.env.local.example web/.env.local` 후 값 채우기.
```

존재하지 않거나 수정이 애매하면 skip. README 대대적 rewrite 금지.

## Acceptance Criteria

```bash
test -f .pre-commit-config.yaml
test -f .gitleaks.toml
test -f .github/workflows/ci.yml
test -f docs/secret-rotation-checklist.md
# .pre-commit-config.yaml 구조 (grep 기반; PyYAML 의존 제거)
grep -q 'gitleaks/gitleaks' .pre-commit-config.yaml
grep -q 'id: gitleaks' .pre-commit-config.yaml
# .gitleaks.toml allowlist에 Phase 1 산출물 example 파일 포함
grep -q 'env\.example' .gitleaks.toml
grep -q 'web/\.env\.local\.example' .gitleaks.toml
# ci.yml 최소 구조 (grep 기반)
grep -q '^name: CI' .github/workflows/ci.yml
grep -q '^on:' .github/workflows/ci.yml
grep -q '^jobs:' .github/workflows/ci.yml
grep -q 'gitleaks:' .github/workflows/ci.yml
grep -q 'gitleaks-action' .github/workflows/ci.yml
# 기존 워크플로는 변경 없음
git diff --quiet HEAD -- .github/workflows/news_collector.yml .github/workflows/news_collector_v2_active.yml .github/workflows/watchdog.yml
# gitleaks 로컬 스캔: 설치돼 있으면 엄격 실행(실패 시 phase 실패), 없으면 skip만 허용.
# `|| true`로 실패를 삼키지 마라.
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-banner --redact --config .gitleaks.toml
else
  echo "gitleaks not installed in runner env; skipping local scan (CI will enforce)"
fi
# 임포트 smoke
python3 -c "from src.pipeline import Pipeline; from src.services.analyzer import HybridAnalyzer"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `tasks/4-round2-hygiene/index.json`의 phase 2 status를 `"completed"`로 변경하라.

gitleaks 바이너리가 runner 환경에 없으면 마지막 scan step은 echo만 남기고 skip한다 (위 AC의 `if command -v` 블록이 이미 처리). 설치돼 있으면 반드시 실행되고, **secret이 검출되면 phase 실패**다. `|| true`로 실패를 묵살하지 마라.

3회 이상 실패 시 `"error"` + `error_message`. 사용자 개입 필요 시 `"blocked"` + `blocked_reason`.

## 주의사항

- **실제 키 rotate는 이 phase에서 수행하지 마라.** 사용자 수동 작업이다. 문서/도구만 준비.
- **`.env` 또는 `web/.env.local` 실제 파일을 만들거나 커밋하지 마라.** example만.
- **example 파일에 실제 값, 의심스러운 placeholder(실제 키 형식 흉내), 과거 노출 값을 넣지 마라.**
- **기존 GitHub Actions 워크플로(`news_collector*.yml`, `watchdog.yml`) 수정 금지.** 새 `ci.yml`만 추가.
- **`CLAUDE.md` 수정 금지.** 사용자 소유.
- **`ci.yml`에 python/web test job stub을 미리 넣지 마라.** Phase 3/4가 해당 파일에 job을 추가하는 방식으로 확장한다.
- `docs/secret-rotation-checklist.md`에 실제 JWT 조각, 키 해시, APP_PASSCODE 값을 절대 기록하지 마라. 커밋 해시만.
- 기존 테스트/동작을 깨지 마라.
