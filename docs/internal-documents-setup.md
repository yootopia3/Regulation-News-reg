# 내부 문서 관리 Stage A 운영 준비

현재 상태: 코드와 로컬 검증 완료, 운영 DB/Storage/관리자 계정/worker 배포는 미적용.
Stage B의 PDF 처리/DB 작업 큐/관리자 실행 화면을 연결했다. 운영 적용은 미완료이며
실행 준비는 `sanction-inspection-execution.md`를 참고한다.
일반 사용자 결과 게시(Stage C)도 추가했다. 상세는 `docs/sanction-inspection-publication.md`.

Report 메뉴에는 `재제공시 리포트`(`/reports/sanctions`) 진입점을 추가했다.
현재 화면은 수집된 공개 공시 검색·종류 선택·기존 요약·원문 조회를 제공한다.
내부 업무문서 기반 부서 매칭이나 게시된 점검 결과를 제공하는 단계는 아니다.

## 지금 사용자가 준비할 사항

1. 아래 변경 파일을 커밋·푸시하고 웹 배포 성공 여부를 확인한다.
   메뉴 반영과 내부 문서 기능 활성화는 별개다.
2. 운영 웹사이트가 연결된 Supabase 프로젝트와 Vercel 프로젝트를 확인한다.
3. 다음 활성화 순서에 따라 migration, 관리자 계정, 서버 환경변수를 설정한다.
   키·비밀번호·HWP 원본을 커밋하거나 채팅에 붙여넣지 않는다.
4. 별도 Python worker를 실행한 뒤 `/admin/documents`에서 HWP를 등록·검토·활성화한다.
5. OpenAI 분석 기능 구현과 계정 데이터 설정 확인 후 실제 분석·게시를 연결한다.

로컬 환경변수에 운영 키가 없다는 사실만으로 Vercel에 키가 없다고 단정하지 않는다.
운영 설정은 해당 관리자 화면에서 확인해야 한다.

## 구현된 화면과 경로

- `/admin/login`: Supabase Auth 이메일/비밀번호 로그인. 서버 `ADMIN_USER_IDS`에 등록된 사용자 ID만 허용.
- `/admin/documents`: HWP 등록, 상태 조회, 목록 페이지네이션.
- `/admin/documents/[id]`: 조문별 부서 후보 수정·검토 저장, 전체 검토 후 활성화, 삭제/재시도.
- 기존 `APP_PASSCODE`와 `mp_session`은 관리자 권한으로 사용하지 않는다.
- 업로드는 인증된 서버 API를 거치며 2MB 이하 HWP v5만 받는다. worker가 실제 HWP 헤더·압축량·본문을 다시 검사한다.
- 원본·추출문은 `internal-documents` private bucket과 신규 비공개 테이블에만 저장한다.
- 일반 사용자에게 문서 API·원본 다운로드·미검토 내용을 제공하지 않는다. 현재 단계는 외부 AI를 호출하지 않는다.

## 활성화 순서

1. Vercel의 `NEXT_PUBLIC_USE_V2_DB`와 대응하는 Supabase URL을 기준으로 대상 프로젝트를 확인한다. 과거 문서의 프로젝트 ID를 그대로 사용하지 않는다.
2. `db/migrations/202609100001_internal_documents.sql`을 검토하고 해당 프로젝트에 적용한다. 신규 테이블/함수와 private bucket을 생성하며 기존 기사 행을 수정하지 않는다.
3. Supabase Auth에서 관리자 계정을 생성하고 확인된 사용자 UUID를 서버의 `ADMIN_USER_IDS`에 등록한다. 여러 ID는 쉼표로 구분한다. 관리 페이지에는 공개 회원가입 기능이 없다.
4. 웹 서버에 해당 프로젝트의 `SUPABASE_SERVICE_ROLE_KEY`를 설정한다. 내부 문서 경로에는 anon key fallback이 없다. 키를 Git/채팅에 넣지 않는다.
5. Python worker를 웹 서버와 같은 DB 프로젝트로 구성한다. backend는 `SUPABASE_URL` 또는 `ENV_TYPE`에 대응하는 기존 설정을 사용하므로 URL이 같은지 반드시 확인한다.
6. worker 전용 환경에 `requirements-documents.txt`를 설치하고 아래 명령을 실행한다.

```text
python -m src.services.internal_documents.worker
```

단일 작업 점검은 `--once`를 추가한다. worker는 기존 공개 collector workflow와 분리된 실행 환경에 배포한다.

7. 합성 파일로 Storage 직접 접근 차단과 관리자 접근을 먼저 확인한다.
8. 웹과 worker의 `INTERNAL_DOCUMENTS_ENABLED=true`를 설정하고 실제 문서를 관리자 화면에서 등록한다. worker가 실행 중이어야 `추출 대기`에서 진행한다.
9. 모든 조문과 경고를 원문에 대조하고 검토를 저장한다. 활성화는 전체 조문 검토 및 경고 확인, 시행일 도래가 필요하다. 같은 문서 종류의 기존 활성 문서는 이전 버전이 된다.

## 세션·제한

- 관리자 access token은 HttpOnly/SameSite=Strict 쿠키에만 저장한다. HTTPS에서 Secure를 적용하며, 로컬 HTTP 개발만 예외다.
- 관리자 세션은 최대 1시간이며 만료 후 다시 로그인한다. refresh token을 브라우저나 DB에 저장하지 않는다.
- 매 API 요청에서 `getUser`와 서버 allowlist를 확인한다. Supabase Auth와 문서 권한 설정이 안 되면 닫힌 상태로 실패한다.
- 로그인 요청은 전역 분당 30회, 이메일별 10분당 5회로 제한한다. 이메일 원문 대신 서버 HMAC 키를 rate-limit 테이블에 기록한다.
- 업로드는 관리자별 시간당 10회 제한이다. 변경 API는 동일 Origin만 허용한다.
- 관리자 문서 응답은 `private, no-store`. 일반 사용자는 신규 테이블을 직접 조회할 수 없다.

## 복구와 삭제

- 업로드 중단으로 `업로드 확인 필요`에 남은 문서는 15분 후 삭제할 수 있다. 활성 업로드와 삭제가 겹치지 않도록 grace period를 둔다.
- enqueue 응답이 유실되더라도 원본을 즉시 삭제하지 않는다. 목록 새로고침으로 실제 DB 상태를 확인한다.
- 추출/삭제 작업은 5분 lease와 최대 3회 재시도를 갖는다. parser의 실행 timeout은 60초다.
- 추출 실패는 재시도할 수 있다. 삭제 실패도 `삭제 실패` 상태에서 다시 삭제 요청할 수 있다.
- 삭제 worker가 원본 객체를 제거한 뒤 추출문을 지우고 tombstone을 남긴다. tombstone에는 문서 ID·해시·행위 이력이 남으며 제목/추출문/경고는 제거한다.
- 삭제 완료 후 동일 파일을 다시 등록할 수 있다. 실행 중인 추출을 삭제하려면 완료 또는 lease 회수를 기다린다.
- backup 만료·보관 정책은 실제 Supabase 계약/설정에서 별도 확인해야 한다. 앱 삭제를 모든 백업에서 즉시 소거됐다고 표시하지 않는다.

## parser 배포 시 확인

- pyhwp 0.1b15, olefile 0.47 기반이다. pyhwp는 AGPL-3.0-or-later이며 서비스/배포에 맞는 라이선스 의무 검토가 필요하다. 별도 프로세스 실행만으로 해당 의무가 없어진다고 간주하지 않는다.
- 원본 HWP 또는 라이브러리 소스는 이 저장소에 복사하지 않았다.
- parser subprocess에 DB/API key를 전달하지 않는다. stdout/stderr는 저장하지 않고, 결과는 작업별 임시 폴더에서 읽은 뒤 제거한다.
- Python audit hook으로 socket 생성/연결을 차단한다. 운영은 Linux 컨테이너에서 비root·읽기전용 앱 파일·프로세스/메모리 제한과 네트워크 격리를 추가해 운영해야 한다. audit hook만을 OS 보안 경계로 간주하지 않는다.
- Linux에서 메모리 512MB, CPU 45초, 결과 파일 32MB 제한을 적용한다. Windows 로컬 검사는 timeout/파일/압축량 제한을 적용하지만 Linux resource limit은 적용되지 않는다.
- HWPX, 암호화·배포용 문서는 현재 지원하지 않는다. 조문 번호 반복/초과 용량/조문 없는 문서는 자동 활성화하지 않는다.

## 검증 명령과 증거

```text
python -m pytest tests/ -q
cd web
npm test
npm run test:documents-db
npm run lint
npm run build
```

DB 테스트는 PGlite의 메모리 DB와 합성 내용만 사용한다. 신규 migration을 실제 실행하고, anon/authenticated의 테이블·함수 접근 차단, 광범위 기존 Storage 정책 하에서도 private bucket 차단, lease·검토·활성화·교체·삭제 복구·중복 해시·요청 제한을 검사한다. 실제 Supabase Storage HTTP 동작이나 운영 정책 적용을 대체하지 않는다.

실제 HWP는 로컬 격리 parser로만 검사해 사전 검증과 같은 110개 조문을 확인했다. 외부 AI 요청은 하지 않았다.

2026-09-10 최종 로컬 검증: Python 133개 통과, 웹 83개 통과,
PGlite migration/권한/생명주기 통합 테스트 통과, ESLint 및 Next.js production build 통과.
기능이 비활성인 상태의 빌드이며 운영 계정으로 업로드한 end-to-end 검증은 아직 아니다.

별도 코드 검토에서 발견한 업로드/삭제 경합, 삭제 실패 복구, tombstone 해시 재등록, 응답 유실 시 원본 보존 문제를 수정했다.
회귀검증 중 기존 테스트의 고정 과거 날짜, 누락된 KFB 네트워크 mock, 변경 전 RSS 자정 정책/기관 약칭 기대값, mock 타입 선언을 바로잡았다. 기존 수집기의 동작은 변경하지 않았다.

운영 활성화 전에는 실제 Supabase의 사용자/버킷/테이블 권한을 별도로 검증해야 한다.
