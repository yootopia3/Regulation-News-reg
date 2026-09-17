# 제재공시 자동 분석·게시

사용자 합의: 수집 배치 후 건별 승인 없이 분석 결과 조회. 내부 원문은 비공개 유지,
검증 실패만 관리자 확인. PC 대신 기존 GitHub Actions 기반 별도 작업 사용.
superpowers 전용 스킬은 로컬 카탈로그/검색에서 발견되지 않아 AGENTS의 단계 자체를 따른다.

## 설계
- 공개 collector 성공 후 default branch의 별도 workflow_run, 수동 workflow_dispatch 지원.
- 활성 규정이 있을 때만 최근 공시 중 미처리 건을 최대 3건씩 enqueue. 실패 자동 재과금 금지.
- 같은 금감원 검사번호/공개순번은 기간 파라미터가 달라도 중복 분석하지 않는다.
- 기존 Python 분석기 확장: 관련 업무를 별도 필드로 생성, 기존 근거 검증 유지.
- 별도 토큰으로 보호한 서버 API가 기존 공개 DTO/내부 원문 유출 검증을 재사용한다.
- 검증 후 단일 CAS RPC로 자동 게시. 관리자 저장·철회·재분석·규정 변경과 충돌하면 중단.
- 기존 게시/초안은 보존. 자동 결과는 명시적 표식, 미매칭/검증 실패는 관리자 확인.
- 기능은 기본 비활성. SQL/웹 배포/Actions 및 Vercel secrets를 설정해야 실제 활성.

## 작업 및 검증
1. schema/RPC, 자동 큐 및 게시 서비스
2. 관련 업무 생성, 배치 실행기/Actions, 화면 표식
3. 단위 테스트: 인증, 범위/중복, 원문 차단, CAS, 철회, 실패 재시도 금지
4. DB integration, Python/web 테스트, lint/build
5. 독립 review lane 및 지적사항 수정
6. 운영 migration과 토큰 설정, 1건 자동 실행 검증; secrets는 채팅/로그/커밋 금지

## 검증 결과
- Python 관련 테스트 50개 통과.
- 웹 전체 136개 및 추가된 별칭/자동 표식 2개 포함 대상 19개 통과.
- 3종 PGlite DB 통합 테스트 통과; production build 통과.
- SQL/앱/배치 독립 리뷰 완료, NULL revision CAS 보강 반영.
- 실제 운영 migration/웹 배포/Actions 설정은 아직 미적용.
