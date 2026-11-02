# 제재공시 AI 연결 설정

## 합의 범위

- 관리자 화면에서 연결 주소, 모델, API 키를 변경한다. 우선 제재공시 심층 보고서에만 적용한다.
- 현재 인터넷 API 사용. 향후 사내 서버 사용을 위해 OpenAI Responses 및 Chat Completions 호환 방식을 지원한다.
- 기존 보고서/게시 절차와 일반 Gemini 분석은 유지한다. 저장한 설정은 다음 작업부터 사용한다.
- 사내망 API 사용 시 웹 서버와 Python worker도 해당 망에 접근 가능해야 한다. 인터넷 배포를 자동으로 사내망에 연결하지 않는다.

## 구현 계획

1. service_role 전용 단일 설정 테이블과 revision CAS 저장 RPC. API 키는 AES-256-GCM 암호문만 저장한다.
2. 기존 관리자 인증/Origin/요청 제한을 재사용한다. 모델 목록 조회, 합성 JSON 응답 시험, 검증된 설정 저장 API를 추가한다.
3. 관리자 설정 화면: 주소, 방식, 모델, 교체용 키, 모델 조회, 연결 시험, 저장. 키는 마지막 4자리만 표시한다.
4. 기존 InspectionClient를 확장한다. 작업 시작마다 DB 설정을 읽고 작업 중에는 고정한다. 환경설정 방식은 미활성 상태의 기본값으로 유지한다.
5. backend/frontend/DB 테스트, type check, lint 및 독립 검토를 거친다. 배포/운영 DB migration은 별도 운영 단계이다.

## 데이터와 연결 경계

- 최초 1회 SANCTION_AI_SETTINGS_ENABLED와 공유 AI_CONNECTION_ENCRYPTION_KEY를 웹/worker에 설정한다. 활성화 후 DB/복호화 오류는 중단하며 구키로 조용히 전환하지 않는다.
- 키가 비어 있으면 동일 주소의 기존 키만 유지한다. 주소 변경은 새 키를 요구한다.
- 시험 성공 영수증은 설정/키/revision/관리자에 결합한 HMAC이며 10분 만료한다. 저장 시 재검증한다.
- DNS 결과를 검증하고 연결 IP를 고정한다. redirect, URL 자격증명, query/fragment, loopback, link-local/metadata 주소는 거부한다.
- 기본은 공개 HTTPS API. 사내 이전 시 운영자가 정확한 base URL을 AI_CONNECTION_PRIVATE_BASE_URLS에 허용하고 사내망에 배포해야 RFC1918/ULA 접근을 허용한다. TLS 검증은 끄지 않는다.
- provider 원문 오류/키/입력 데이터는 응답과 로그에 남기지 않는다. 모델 시험은 합성 문장만 전송한다.
- Chat Completions는 JSON mode + 스키마 지시를 사용하고 기존 Pydantic/근거/게시 검증을 유지한다. 호환 모델이 JSON 형식 또는 충분한 문맥 길이를 지원하지 않으면 실패로 처리한다.

## 검증 항목

- 비관리자/다른 Origin 거절, 암호문/키 비노출, 변경된/만료된 시험 영수증 거절, CAS 충돌.
- SSRF/혼합 DNS/redirect/응답 크기·시간 제한 및 명시적 사내 주소 허용.
- Node 암호화 → Python 복호화 상호운용, 양쪽 요청/응답 형식, 작업별 설정 변경 반영.
- 기존 Responses 동작과 자동 게시 경로 회귀 테스트.

참고: [OpenAI JSON mode / Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## 구현 및 검증 결과

- 관리자 UI/API, 암호화 저장/CAS, 모델 목록/합성 연결 시험, 두 프로토콜, 작업별 설정 재조회 구현.
- 독립 검토에서 지적한 시험/실제 출력 한도 차이, 주소 변경 시 입력 키 초기화, 429 잔액 오류 보존 수정 완료. 재검토에서 추가 차단 사항 없음.
- Python 전체 430개 통과 (`-X utf8`, Windows 기본 인코딩 영향 방지).
- 웹 전체 252개 통과 (로컬 Excel 모듈 초기 로딩을 위해 CLI testTimeout=15000).
- 신규 PGlite DB 권한/저장/충돌 검사, TypeScript, 변경 파일 ESLint, diff whitespace 검사 통과.
- Next.js production build `--webpack` 통과. 기본 Turbopack은 기존 node_modules junction이 작업 폴더 밖을 가리켜 실패; 앱 설정 변경 없이 지원 빌드 방식으로 검증.
- 합성 데이터로 실제 페이지 코드를 정적 미리보기 파일에 렌더링함. 내장 브라우저는 file URL 정책으로 열기를 거부하여 화면 스크린샷 검증은 수행하지 못함.
- 운영 DB migration, 서버 비밀 설정, 실제 provider 호출, commit/push/운영 배포는 미실행.
