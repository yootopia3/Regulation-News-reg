# 관리자 AI 연결 설정

제재공시 심층 보고서만 대상으로 한다. 일반 보도자료/Gemini 및 기존 게시본은 바꾸지 않는다.
화면 위치: `/admin/ai-connection` (내부 문서 관리와 제재공시 분석 관리의 상단 링크).

## 최초 운영 설치

1. DB 백업 후 `db/migrations/202611020001_ai_connection.sql`을 적용한다.
   새 service_role 전용 테이블/RPC만 추가하며 기존 분석/게시 테이블은 변경하지 않는다.
2. 암호학적 난수 32바이트의 64자리 hex 값을 생성하여 웹 서버(Vercel)와 모든 Python worker에
   동일한 `AI_CONNECTION_ENCRYPTION_KEY`로 비밀 저장한다. 채팅·Git·공개 환경변수·로그에 넣지 않는다.
   GitHub Actions에서는 동일 이름의 repository secret을 사용한다.
3. 웹과 worker 모두 `SANCTION_AI_SETTINGS_ENABLED=true`로 설정한다.
   Actions는 동일 이름의 repository variable을 사용한다. 기존 관리자 인증, DB 접속 설정,
   `SANCTION_INSPECTIONS_ENABLED`, `OPENAI_INSPECTION_POLICY_CONFIRMED` 게이트도 유지한다.
4. 웹/worker 코드를 함께 배포하고 관리자 로그인 → AI 연결 설정을 연다.
   새 설정을 처음 저장하기 전에는 기존 `OPENAI_*` 환경설정으로 분석한다.
5. 연결 주소, 방식, 모델, API 키 입력 → 필요시 모델 목록 조회 → 연결 시험 → 설정 저장.
   Responses는 기존 OpenAI 방식, Chat Completions는 JSON mode를 지원하는 호환 서버용이다.
   연결 시험은 합성 문장만 보내고 실제 보고서와 같은 최대 출력 한도(12,000)를 전달한다.
   작은 시험 통과가 실제 보고서의 긴 입력 처리나 분석 품질을 보증하지는 않는다.
6. 다음 배치/로컬 worker 작업부터 새 설정을 읽는다. 진행 중 작업은 시작 당시 설정으로 마친다.
   기존 게시본은 유지하며 다시 만들려면 해당 공시에서 재분석을 요청한다.

모델 목록 API를 지원하지 않는 서버는 이름을 직접 입력하고 연결 시험을 사용한다.
주소 변경은 새 키 입력을 요구하며 입력 중인 키도 초기화한다. 같은 주소에서 빈 키는 기존 키 유지이다.
연결 시험은 저장하지 않는다. 성공 결과는 관리자·설정·키·revision에 결합되어 10분 동안 유효하다.
두 관리자가 동시에 수정하면 나중 저장은 충돌 처리하므로 새로고침 후 다시 시험해야 한다.

## 사내망 이전

웹 서버, Python worker, DB 접속을 회사가 허용하는 네트워크에서 준비해야 한다.
인터넷 Vercel/GitHub-hosted runner가 사내 주소에 접근할 수 있다고 가정하지 않는다.
현 GitHub workflow는 ubuntu-latest이므로 사내망 전용 API에는 사내 worker 또는 별도 승인된
self-hosted runner 배치가 필요하다. 인터넷 배치와 사내 배치를 동시에 돌리지 않도록 운영자가 전환한다.

사내 API의 **정확한 base URL**을 웹/worker의 `AI_CONNECTION_PRIVATE_BASE_URLS`에 동일하게 지정한다
(여러 개면 쉼표 구분). 명시된 base에만 RFC1918 또는 IPv6 ULA 접근을 허용한다.
예: 사내 HTTPS 이름과 포트 및 `/v1`까지 포함한다. HTTP는 허용한 사내 주소에서만 가능하다.
loopback/link-local/metadata 주소는 허용 목록과 관계없이 차단한다. TLS 인증서는 계속 검증한다.
사설 CA가 있으면 Node/Python 런타임의 신뢰 CA에 설치한다. TLS 검증을 끄지 않는다.

## 키 관리와 복구

- API 키는 AES-256-GCM 암호문으로 DB에 저장하며 API 응답은 끝 4자리만 반환한다.
  암호화 AAD에 base URL을 포함한다. 원문 키, 암호문, provider 원문 오류를 로그에 출력하지 않는다.
- 활성화 후 DB/암호화 키/암호문 오류가 생기면 분석을 중단한다. 과거 API 키로 조용히 재시도하지 않는다.
- 암호화 키를 변경하면 기존 암호문을 읽을 수 없으므로 배치를 멈춘 뒤 웹과 worker 양쪽 값을 맞추고
  관리자 화면에서 API 키를 새로 입력·시험·저장한다. 이전 암호화 키는 안전한 비밀 저장소에서 관리한다.
- 기능 되돌리기: 배치를 멈추고 기존 `OPENAI_API_KEY`, `OPENAI_INSPECTION_MODEL`, 정책 게이트가
  유효한지 확인한 뒤 웹/worker의 `SANCTION_AI_SETTINGS_ENABLED=false`로 전환한다.
  DB 설정은 보존되지만 무시한다. 이후 배치를 재개한다. 키가 폐기됐다면 먼저 갱신한다.

## 개발 검증

- `python -m pytest -q tests/unit/test_ai_connection.py` 및 기존 inspection tests.
- `cd web` 후 `npm test`, `npm run test:ai-connection-db`, `npx tsc --noEmit`, 변경 파일 ESLint.
- Node/Python 암호화 상호운용, 비관리자/다른 Origin, 시험 결과 변조·만료, CAS 충돌,
  DNS 혼합 응답·IP 고정·redirect 거부·응답 제한, 작업 시작 시 재조회 등을 합성 데이터로 검사한다.

참고: [OpenAI JSON mode / Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
