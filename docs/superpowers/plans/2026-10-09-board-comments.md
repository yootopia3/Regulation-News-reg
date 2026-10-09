# 플랫폼 v3 표기 및 게시판 댓글

사용자 요청: Sidebar 하단 v2.0.0을 v3.0.0으로 변경, 스크랩 보관함 제거, 게시글 댓글 추가.
기준: 기존 checkout에서 origin/main 559a9a6 기반 feat/platform-v3-board-comments.
인계 브랜치와 기존 platform_report_source.md는 보존한다. 운영 DB·workflow·배포를 실행하지 않는다.

## 설계

- 기존 게시판 인증과 BOARD_ENABLED를 재사용한다. 댓글은 게시된 글에서만 조회/작성/수정/삭제한다.
- 작성자 이름(1~40자), 내용(1~2,000자), 댓글 비밀번호(8~128자)로 작성한다.
- 본인 인증된 계정 이름은 아니다. 댓글별 scrypt+salt를 저장하고 비밀번호/해시는 응답에 포함하지 않는다.
- 수정/삭제는 댓글 비밀번호 또는 기존 게시판 관리자 인증으로 허용한다. 작성자 이름은 수정하지 않는다.
- 최신순 20개 pagination, 일반 텍스트 표시, 빈/로딩/오류·재시도·처리 중 상태를 제공한다.
- 댓글 삭제는 확인 단계가 있고 글 삭제 시 댓글은 FK cascade로 함께 삭제한다.
- 대댓글·첨부·알림·새 계정 체계는 이번 범위에 포함하지 않는다.

## 구현 순서

1. Sidebar 두 가지 변경. 댓글 schema/migration, 타입, 서버 helper, 두 API route.
2. 별도 hook과 댓글 UI를 게시글 상세 하단에 연결한다. 기존 글·첨부 API 계약은 유지한다.
3. 세션/Origin/flag/rate limit, 비밀번호/관리자, 타 게시글 ID, draft 비노출, revision 충돌,
   응답 비밀 필드 제외, validation, SQL 권한/제약/cascade/게시 상태 및 UI lifecycle을 검사한다.
4. 관련 웹 회귀·DB·타입·ESLint·빌드를 실행한다. AGENTS.md의 별도 context 검토를 받는다.
5. SCHEMA/ARCHITECTURE/board-setup에 데이터와 적용 순서를 기록한다.

## 동시성·권한

board_comments는 service_role 전용 RLS 테이블이다. parent status를 공유 잠금으로 확인하는
INSERT/UPDATE/DELETE trigger로 게시 취소와 댓글 쓰기 경쟁을 직렬화한다. 부모 삭제에 따른 cascade는 허용한다.
조회는 부모의 공개 여부를 먼저 확인하고 목록 쿼리에서도 공개 상태를 필터링한다.
댓글 mutation은 post_id+id+revision으로 범위를 제한한다. 기존 게시판 쓰기 제한 및 댓글별 비밀번호 제한을 적용한다.
문자열을 HTML로 실행하지 않는다. DB 오류/인증값/본문을 로그에 출력하지 않는다.

## 적용 한계

댓글에는 신규 migration 202610090001_board_comments.sql이 필요하다.
개발 검증은 mock/PGlite를 사용하며 운영 migration 실행과 코드 배포는 별도 단계다.

## 검증 결과 (2026-10-09)

- Node 20.20.2에서 웹 전체 테스트 30개 파일 / 202개 PASS.
- 별도 검토 후 수정된 댓글 API/화면/Sidebar 회귀 테스트 3개 파일 / 28개 PASS.
- PGlite DB 검증 6개 모음 PASS. 삭제 guard 보완 후 게시판 DB 검증 다시 PASS:
  일반 role 접근 차단, CAS, 비공개 댓글 쓰기/삭제 차단, 공개 댓글 삭제, 공개/비공개 부모 cascade.
- TypeScript 및 ESLint PASS. 기존 checkout의 오래된 Next.js 개발 route 타입은 재생성했으며
  next-env.d.ts를 포함한 manifest/lockfile에 최종 변경이 없다.
- AGENTS.md에 따른 별도 context 검토에서 게시 취소와 댓글 삭제 사이의 경쟁 상태를 발견해
  DELETE trigger와 안전한 오류 매핑을 추가했다. 재검토에서 추가 중대 문제 없음.
- Next.js 전체 빌드는 Google Fonts 다운로드 단계에서 실패했다. 시스템 인증서 옵션을 사용하고
  샌드박스 밖에서도 같은 프록시·TLS 검증으로 재시도했으나 동일했다.
  fonts.googleapis.com HEAD 요청은 CONNECT 403 Forbidden이며 현재 런타임 허용 목록에 폰트 도메인이 없다.
  빌드 성공으로 표시하지 않는다. 프록시 우회나 TLS 검증 비활성화는 사용하지 않았다.
- 실제 Supabase/PostgREST, 운영 브라우저 및 다중 연결 동시성 실행은 검증하지 않았다.
  운영 DB 적용/배포/앱 외부 API 호출/commit/push는 실행하지 않았다.

## 대상 저장소 정정 (2026-10-09)

사용자가 orbzodiac84/Regulation-News-reg는 과거 샘플 저장소이며 현재 프로젝트가 아니라고 확인했다.
현재 작업/PR 대상은 최초 지정한 yootopia3/Regulation-News-reg이다.
샘플 저장소를 대상으로 확인하던 PR #10 및 Vercel 승인 흐름은 이 작업의 운영 반영 절차가 아니다.
잘못 추가한 샘플 main 병합 8f7712b의 파일 변경을 되돌렸다.
애플리케이션 소스는 원래 요청한 기능 커밋 c7486a8과 동일하며, 이 정정 기록만 별도로 추가한다.
원격 origin을 보존하고 잘못 추가한 upstream remote를 제거했다.
PR 생성 시 저장소 이름만 아니라 base repository owner가 yootopia3인지 반드시 확인한다.
샘플 저장소 main 병합·운영 DB 변경·배포를 직접 실행한 사실은 없다.
