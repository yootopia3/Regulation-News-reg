# 게시판 설계 및 구현 계획

합의: Report를 게시판으로 바꾸고 모든 플랫폼 이용자가 이름과 글별 비밀번호로 작성한다.
본인 글 수정·삭제는 글 비밀번호, 관리자 전체 글 관리·공지 고정은 기존 Supabase 관리자 계정으로 확인한다.
기존 아침에 읽는 규제변화는 게시판 내 바로가기로 유지한다.

## 범위
- 목록/검색/분류/페이지 이동, 상세, Markdown 기본 편집·미리보기, 작성/수정/삭제.
- 임시저장/게시/게시 취소, 관리자 공지 고정. 익명 작성자의 임시글은 관리 링크+비밀번호로 접근.
- PDF/HWP/HWPX/DOC/DOCX/XLS/XLSX, 최대 3개·합계 3 MiB. Vercel 요청 크기 제한 아래로 제한.
- 댓글, 회원가입, 비밀번호 재설정, 조회 수/방문 통계는 범위 밖.

## 구조와 권한
- /board, /board/new, /board/[id], /board/[id]/edit. 기존 일반 세션 필수.
- 전용 board_posts 테이블 및 비공개 board-attachments Storage. 기존 기사/제재 데이터와 독립.
- 글에 첨부 메타데이터를 JSONB로 원자 저장. 비밀번호는 scrypt+임의 salt, 응답에서 해시/저장 경로 제외.
- 서버 API에서 세션·Origin·본문 크기·파일 형식·비밀번호·관리자 권한을 검사한다.
- DB rate-limit RPC로 요청/글별 비밀번호 대입 제한. revision 조건으로 동시 수정 충돌 방지.
- 게시 중인 글만 일반 조회/검색/다운로드. 관리자 또는 비밀번호 인증한 편집 응답만 임시글 반환.
- HTML 실행·외부 이미지 임베딩 없이 안전한 Markdown 표시. 첨부파일은 다운로드 응답으로만 제공.
- 기존 관리자 인증의 scope 기본값은 documents로 보존하고 board는 BOARD_ENABLED로 별도 활성화한다.

## 실행 순서
1. migration, 검증/암호/저장/첨부/API 구현.
2. 목록/상세/편집/관리자 로그인 UI, Report 메뉴 연결.
3. API·컴포넌트·비밀번호 테스트, PGlite 권한/제약/경쟁 검사, 웹 회귀 테스트·타입·린트·빌드.
4. AGENTS.md 요구에 따른 별도 context 코드 리뷰와 피드백 반영.
5. SCHEMA/ARCHITECTURE 및 운영 설치 절차 갱신. DB migration은 개발 중 운영에 실행하지 않는다.

## 운영 적용
코드 배포 전에 전용 migration 적용 및 private Storage, BOARD_ENABLED=true와 서버 DB 설정 확인 필요.
일반 게시판은 ADMIN_USER_IDS 없이 사용할 수 있고 관리자 기능만 관리자 계정 설정이 필요하다.
이 대화에는 운영 DB 연결 자격증명이 없으므로 로컬 PGlite와 mock 검증을 사용한다.

## 검증 및 리뷰 결과 (2026-10-05)
- 웹 전체: 27 files / 172 tests PASS (게시판 API/화면 20 tests 포함).
- `npm run test:documents-db`: 기존 5개 DB 스크립트 및 신규 게시판 스크립트 PASS.
- TypeScript noEmit 및 웹 전체 ESLint PASS. Node 24.19.0에서 실행했으며 CI Node 20 검증은 별도다.
- 별도 context 리뷰의 관리 링크 재진입/관리자 로그아웃 지적을 수정하고 재검토 완료.
- `npm run build`: 기존 Geist/Geist Mono Google Fonts 다운로드가 Cloud 네트워크에서 실패.
  따라서 운영 빌드 성공과 실제 Supabase/Vercel 통합 검증은 아직 완료로 간주하지 않는다.
- 실제 운영 DB/API 호출, DB migration 적용은 실행하지 않았다.
