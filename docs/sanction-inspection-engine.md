# 제재 점검 분석 엔진 — Stage B 일부

## 구현 상태

`src/services/sanction_inspections/`는 페이지별 공개 제재 텍스트와 검토·활성화된
내부 조문을 입력받아 관리자 검토용 초안을 반환하는 라이브러리다.
기존 수집기·Gemini·일반 기사 테이블에 연결하지 않았다. 별도 관리자 실행 큐 연결은
`sanction-inspection-execution.md`에 기술한다.
실제 HWP나 API 키를 이용한 호출은 수행하지 않았다.

- 1차 요청: 공개 텍스트에서 지적사항·페이지·짧은 인용을 구조화한다.
- 로컬 검색: 한국어 2글자 부분어 일치로 최대 6개 부서 조문을 고른 뒤
  같은 문서의 교차 참조를 확장한다. 최대 12개 조문/지적사항, 24,000자다.
  전체 2차 요청의 내부 본문 합계는 60,000자 이하이며 초과 시 검토 필요 오류다.
  이름이 붙은 법령/규정 참조와 조문 범위 참조는 자동 해석하지 않고 검토를 요구한다.
- 2차 요청: 선택된 조문으로만 부서 후보·업무 관련성·점검 질문·요청 증빙을 제안한다.
- 검증: 페이지 인용, 조문 인용, 담당 부서 근거, 지적사항 누락/중복을 검사한다.
  담당 부서명은 검토된 조문에서 가져오며 AI의 임의 부서 문자열은 받지 않는다.
- 결과: 항상 `needs_review`. 공개 응답이나 게시본으로 사용하면 안 된다.
  `findings`, `matches`, `document_versions`, `fingerprint`와 미매칭 ID를 포함한다.

내부 조문의 원문·단축 인용은 관리자용 결과에도 포함될 수 있다. 일반 API로 반환하지 않는다.
40자 이상 연속 복사 탐지는 추가 방어이며 재서술·분할 인용 유출이나 업무 관련성을
보증하지 않는다. 관리자 검토와 게시용 필드·문자열 검사(Stage C)가 별도로 필요하다.
단순 부분어 검색의 정확도와 공개 지적사항 분리 완전성은 실제 사례로 평가해야 한다.

## 설정과 호출

별도 처리 환경에서 `requirements-inspections.txt`를 설치한다.
`Settings.from_env()`는 아래 값이 준비되기 전 전송을 차단한다.

- `SANCTION_INSPECTIONS_ENABLED=true`
- `OPENAI_INSPECTION_POLICY_CONFIRMED=true`: 담당자가 실제 API 프로젝트의 공유/보관 설정을 확인한 후 설정한다.
- `OPENAI_INSPECTION_MODEL`: 해당 계정에서 이용 가능한 Structured Outputs 지원 모델.
- `OPENAI_API_KEY`: 비밀 설정에만 저장.

키 확인용 전용 도구는 이번 환경에 제공되지 않아 모의 전송으로 검증했다.
`OPENAI_INSPECTION_POLICY_CONFIRMED`는 계정 설정을 변경하거나 자동 검사하는 값이 아니다.

Responses API에 `store=false`, `background=false`, 출력 한도를 명시한다.
파일 업로드·도구·대화 ID·자동 재시도·다른 공급자 fallback은 사용하지 않는다.
고정 HTTPS endpoint에만 요청하고 리다이렉트, 환경 프록시 및 `.netrc` 사용을 차단한다.
응답은 1MB로 제한하고 오류는 내용 없는 코드로 반환한다.

OpenAI API 데이터는 기본적으로 학습에 사용되지 않지만 계정의 공유 opt-in 여부를 확인해야 한다.
`store=false`가 악용 모니터링 로그까지 없애는 것은 아니며, 통상 최대 30일 보관과
별도 승인받는 ZDR 조건을 확인해야 한다.
[공식 데이터 정책](https://developers.openai.com/api/docs/guides/your-data),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## 실행 연결 상태

1. 공개 PDF 다운로드와 격리 페이지 추출을 구현했다. 이미지 페이지 OCR은 미구현이다.
2. worker가 활성 문서와 조문을 읽고 버전 변경을 확인한다. Unit의 active/reviewed 값은
   반드시 DB에서 계산해야 하며 사용자 요청 값을 신뢰하면 안 된다.
3. 비공개 작업 큐·lease·결과 저장·관리자 실행/초안 조회 화면을 추가했다.
4. Stage C 관리자 수정·게시 검토를 거친 결과를 `Report → 재제공시 리포트`에 제공하도록 연결했다.

라이브러리와 관리자 실행 연결을 구현했지만 운영 활성화로 간주하지 않는다.

검증: 합성 입력과 모의 API로 Python 전체 164개 테스트 통과.
별도 검토에서 발견한 외부 법령 오연결·범위 중간 조문 누락을 차단하고 회귀 테스트를 추가했다.
