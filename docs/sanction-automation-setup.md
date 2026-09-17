# 제재공시 자동 분석·게시 운영 설정

## 동작
기존 수집 workflow가 성공하면 별도 `Sanction Analysis and Publication` 작업이 실행된다.
PC 없이 GitHub의 실행 서버에서 1회 최대 3건을 처리한다. 신규 작업은 설정 기준일 이후,
최근 90일 공시에 한정하며 같은 검사번호/공개순번의 다른 검색 URL은 재분석하지 않는다.
예전 미처리 공시를 포함하려면 기준일을 과거로 설정한다. 3건 초과는 다음 배치에서 처리한다.
수집기 자체/Gemini/일반 보도자료 보고서는 변경하지 않는다.

자동 결과는 공개 근거, 활성 규정 버전, 전체 지적사항 매칭, 공개 DTO,
내부 원문 인용/24자 연속 복사/메타데이터 노출 검사를 통과해야 게시된다.
이는 의미상 모든 기밀 유출을 자동 판별한다는 보장은 아니다.
표시: `AI 자동 분석 · 담당자 확인 필요`. Excel에도 동일 문구를 넣는다.
관련 업무도 생성한다. 관리자 수정·게시·철회는 유지하며 자동 배치가 이를 덮어쓰지 않는다.

이미지 PDF/OCR 필요, 근거 부족, 미매칭, 분석 오류는 관리자 확인 대상으로 남는다.
AI 오류/규정 변경 작업을 배치가 반복 재분석하지 않는다. 명시적 `다시 분석`은 재과금될 수 있다.
게시 통신 실패만 다음 배치에서 다시 시도하며 AI를 다시 호출하지 않는다.
관리자 `분석 실행`으로 만든 대기 작업도 다음 배치가 처리한다.

## 적용 순서 (중요)
1. Supabase SQL Editor에서 `db/migrations/202609170001_sanction_automation.sql` 전체 실행.
   앞선 세 migration이 적용된 프로젝트에만 적용한다. 기존 게시본/검토본은 보존한다.
   앱이 새 컬럼을 조회하므로 **이 단계를 웹 배포보다 먼저** 완료한다.
2. 코드 커밋·푸시 → Vercel `regulation-news-reg-fiu7` Ready 확인.
3. 긴 무작위 전용 토큰을 생성한다. 로컬에서 생성 예:
   Python `secrets.token_urlsafe(48)`을 사용해 Git 제외 `.env`에 직접 기록한다.
   키/토큰/내부 문서는 채팅·Git·workflow 로그·artifact에 넣지 않는다.
4. Vercel Production 환경변수:
   - `SANCTION_AUTOMATION_TOKEN`: 위 토큰, Secret
   - `SANCTION_AUTOMATION_ENABLED=true`: Config
   - 기존 INTERNAL_DOCUMENTS_ENABLED / SANCTION_PUBLICATIONS_ENABLED 및 관리자/DB 설정 유지.
   - 변경 후 Redeploy. OpenAI 키는 Vercel에 추가할 필요 없다.
5. GitHub 저장소 Settings → Secrets and variables → Actions → Secrets:
   - `OPENAI_API_KEY`: API 프로젝트 키
   - `SANCTION_AUTOMATION_TOKEN`: Vercel과 동일한 토큰
   - 기존 `NEXT_PUBLIC_SUPABASE_URL_V2`, `SUPABASE_SERVICE_ROLE_KEY_V2`: 같은 Supabase 프로젝트
6. 같은 화면 Variables:
   - `OPENAI_INSPECTION_MODEL=gpt-4.1` (현재 시범 분석에 검증한 모델)
   - `OPENAI_INSPECTION_POLICY_CONFIRMED=true`: 데이터 공유/보관 정책 확인 후
   - `SANCTION_WEB_URL=https://regulation-news-reg-fiu7.vercel.app`
   - `SANCTION_AUTOMATION_SINCE=2026-09-17T00:00:00+09:00`: 원하는 시작 기준일
   - **마지막으로** `SANCTION_AUTOMATION_ENABLED=true`
7. Actions → Sanction Analysis and Publication → Run workflow → main.
   실행 로그에는 건수만 출력한다. 실제 내부 문서를 자동 게시하기 전 설정과 공개 결과를 점검한다.
8. 관리자 분석 관리에서 `AI 자동 게시 완료` 확인, 대시보드 카드에서 자동 분석 표식/내용/Excel 확인.
   `자동 처리 보류 · 관리자 확인 필요`는 초안을 열어 검토한다.

## 중지와 복구
GitHub Variables 및 Vercel의 SANCTION_AUTOMATION_ENABLED를 false로 바꾸고 웹을 재배포한다.
이미 게시된 결과는 계속 조회된다. 숨기려면 관리자 게시 철회를 사용한다.
중단된 AI 작업은 15분 lease 만료 후 failed로 회수되며 자동 AI 재호출은 하지 않는다.
토큰 회전은 Vercel과 GitHub 양쪽에서 같은 값으로 교체하고 Vercel 재배포가 필요하다.

## 로컬 시범 실행
서버 설정 완료 후 Git 제외 `.env`에 같은 자동화 변수/토큰을 설정하고:
`python -m src.services.sanction_inspections.batch`
실행량 기본 3, 1~10 범위. 신규 모델 응답에 related_work가 있어야 자동 게시된다.
이전 초안/기존 사람이 게시한 결과는 자동으로 수정하지 않는다.

## 검증 범위
합성 입력 단위/메모리 DB 테스트와 빌드는 실제 운영 자동화 검증을 대체하지 않는다.
운영 토큰·Actions 변수 설정 및 신규 migration 적용 전에는 자동 실행되지 않는다.
