# 제재공시 분석 실행 운영 준비

현재 코드에는 PDF 다운로드/격리 추출, 비공개 작업 큐, worker,
관리자 실행·초안 조회 화면이 연결되어 있다. 실제 운영 DB 적용·배포·AI 호출은 미실행이다.

## 사용 경로

`Report → 재제공시 리포트 → 관리자 분석 실행`에서 별도 관리자 로그인 후 사용한다.
최근 공시 100건 중 선택해 실행하고 새로고침으로 진행 상태를 확인한다.
최근 작업 50건의 초안을 확인할 수 있다. 초안에는 부서 후보, 관련성, 점검 질문,
요청 증빙, 공개 PDF 페이지 인용과 관리자 전용 내부 근거가 포함된다.
관리자 수정·게시·철회 및 일반 사용자 조회·Excel 기능은 `sanction-inspection-publication.md`를 참고한다.

## 운영 설정 순서

1. 웹과 worker가 사용하는 Supabase 프로젝트가 같은지 확인한다.
2. 기존 문서 관리 migration `202609100001_internal_documents.sql` 다음에
   `db/migrations/202609100002_sanction_inspections.sql`을 적용한다.
3. 기존 관리자 Auth/allowlist/service-role 설정과 HWP worker를 준비하고
   업무규정을 등록·전체 검토·활성화한다. 상세는 `internal-documents-setup.md`.
4. 별도 Python 실행 환경에 `pip install -r requirements-inspections.txt`를 실행한다.
   HWP worker와 같은 환경이면 `requirements-documents.txt`도 별도로 설치한다.
5. 웹에 `SANCTION_INSPECTIONS_ENABLED=true`를 설정한다. 관리자 접근에는
   기존 `INTERNAL_DOCUMENTS_ENABLED=true`와 관리자 키 설정도 필요하다.
6. 분석 worker에 Supabase service-role/대상 URL과 다음 설정을 비밀 환경변수로 넣는다.
   `SANCTION_INSPECTIONS_ENABLED=true`, `OPENAI_INSPECTION_MODEL`, `OPENAI_API_KEY`,
   실제 API 프로젝트 공유·보관 정책 확인 후 `OPENAI_INSPECTION_POLICY_CONFIRMED=true`.
7. `python -m src.services.sanction_inspections.worker`를 공개 collector와 분리해 실행한다.
   한 작업만 점검하려면 `--once`를 추가한다. 코드·로그에 문서/키를 넣지 않는다.
8. 관리자 화면에서 한 공시를 실행하고 초안을 원문·내규와 대조한다.

## 제한 및 복구

- DB에 등록된 `articles.analysis_result.pdf_url`만 사용한다. 사용자가 URL을 넣을 수 없다.
- FSS의 HTTPS 두 호스트(`www.fss.or.kr`, `fss.or.kr`)만 허용한다.
  DNS 결과에 사설/비공개 IP가 있으면 거부하고 검증 IP로 연결한다.
  TLS 검증·호스트 검증은 끄지 않는다. 리다이렉트도 동일 검사를 적용한다.
- PDF 최대 10MB, 200쪽, 한 쪽 12,000자, 전체 80,000자다.
  parser는 별도 프로세스에서 60초 제한, Linux 메모리 512MB/CPU 45초 제한으로 실행한다.
  PDF 처리에 키를 전달하지 않으며 네트워크 audit hook을 적용한다.
  운영은 HWP parser와 마찬가지로 컨테이너/비root/네트워크 격리 등 OS 경계가 필요하다.
- **이미지가 있는 페이지는 로고만 있어도 OCR 필요로 중단한다.**
  텍스트 머리말과 이미지 본문이 섞인 문서의 지적사항을 누락하지 않기 위한 현재 제한이다.
  20자 미만 페이지·암호화 PDF도 자동 분석하지 않는다. OCR은 아직 연결하지 않았다.
- 작업은 15분 lease를 가진다. 만료 작업은 worker가 다음 claim 시 실패 처리한다.
  자동 AI 재호출은 없으며 실패 후 관리자가 다시 실행한다.
- 완료 초안도 `다시 분석`으로 현재 원문·모델 설정에 맞춰 다시 생성할 수 있다.
  재실행은 기존 초안을 교체하며 AI 비용이 다시 발생할 수 있다.
  같은 요청 ID의 재전송은 같은 작업을 반환하고 대기/진행 중인 중복 요청을 합친다.
- 활성 규정 버전이 변경되면 해당 버전 집합을 사용한 초안·작업은 stale 처리하고
  결과를 삭제한다. 처리 중 변경되어도 이전 lease로 결과를 다시 저장할 수 없다.
- 일반 기사 테이블에는 내부 분석을 저장하지 않는다. 신규 테이블과 API는 관리자 전용이다.
- 기능을 끄려면 웹·worker의 `SANCTION_INSPECTIONS_ENABLED=false`와 worker 중지를 적용한다.
  기존 초안 조회 권한은 계속 관리자에게만 있다.

## 검증 범위

합성 PDF 실제 격리 추출, 모의 외부 호출, 메모리 DB migration/권한/lease/
문서 변경 무효화/명시적 재실행, 관리자 API·화면 테스트로 검증한다.
실제 Supabase 권한 설정과 운영 AI 품질 검증을 대체하지 않는다.
