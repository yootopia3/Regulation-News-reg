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
- [ ] Vercel 배포 후 `/login` → `/` 정상 동작, `GEMINI_ENABLED=false` 상태에서는 `/api/report`가 503 비활성 응답
- [ ] GitHub Actions `news_collector_v2_active.yml` 수동 트리거 후 성공
