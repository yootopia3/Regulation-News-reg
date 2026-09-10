# Stage B 실행 연결

관리자만 기사 ID로 분석을 요청한다. 서버가 제재 카테고리와 PDF URL을 조회하며
사용자 URL/내부 조문 입력을 받지 않는다. 일반 Report 화면에는 초안을 노출하지 않는다.

1. FSS HTTPS PDF만 DNS/IP/redirect/용량/시간을 검사해 다운로드한다.
   기존 수집 HTTP helper는 TLS opt-out을 지원하므로 이 경계에는 사용하지 않는다.
2. 기존 격리 프로세스 runner를 재사용해 PDF 페이지 텍스트를 추출한다.
   암호화/스캔/과대 PDF는 명시적으로 실패한다.
3. service_role 전용 작업 테이블과 enqueue/claim/finish RPC를 추가한다.
   기사당 단일 작업, 15분 lease, 자동 유료 재호출 없음, 명시적 재실행을 제공한다.
   활성 문서 버전을 고정하고 문서 변경/삭제 시 초안을 지우고 stale 처리한다.
4. worker가 활성·검토 조문을 1000행 페이지네이션으로 읽고 기존 엔진을 호출한다.
5. 별도 관리자 화면에서 공시 선택·실행·상태·초안을 확인한다.
   게시/일반 사용자 공개는 Stage C에서 추가한다.
6. 합성 PDF/DB/모의 API와 권한 테스트, 빌드, 별도 검토로 검증한다.

운영 migration·계정 키·worker 배포 및 실제 AI 품질 평가는 별도 운영 설정이 필요하다.

로컬 검증: Python 177개 통과, 두 migration 통합 DB 테스트 통과,
ESLint 및 Next.js production build 통과. 별도 검토의 혼합 스캔 누락 및
완료 초안 재분석 불가 문제를 수정했다. 운영 적용은 미실행이다.
