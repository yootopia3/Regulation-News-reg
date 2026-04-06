# Refactor Round 1 — Backend Structure Cleanup

MVP에서 그대로 자란 백엔드(`src/`)의 구조를 정리한다. 이번 라운드는 안전 우선:
동작 변경 0건, 스키마 변경 0건, 프론트/잡파일 손대지 않는다.

> runner 실행 전 의존성 설치(`pip install -r requirements.txt`)는 사용자가 1회
> 수동 수행한다. 각 phase의 AC는 import smoke test만 사용한다.

## 1. 목적

`pipeline.py` / `scraper.py` / `analyzer.py`에 책임이 뭉쳐 있고, 설정·DB·문자열
리터럴이 흩어져 있다. 동작은 그대로 둔 채 모듈 경계와 개발자 원칙(SRP, 상수화,
의존성 방향)을 정리해 이후 작업(MOEF 소스 교체, 성능 개선 등)을 할 수 있는
바닥을 만든다.

## 2. 현재 동작 (변하면 안 되는 것)

- 실행 흐름: cron-job.org → GitHub Actions(`news_collector_v2_active.yml`) →
  `python src/main.py`.
- 9개 agency 수집:
  - RSS: `FSC`, `MOEF`
  - scraper: `FSS`, `BOK`, `FSS_REG`, `FSC_REG`, `FSS_REG_INFO`
  - sanction scraper: `FSS_SANCTION`, `FSS_MGMT_NOTICE`
- 일반 link 중복 체크 + 제재 고유키(`examMgmtNo`, `emOpenSeq`) 중복 체크 두 가지가
  공존한다.
- cutoff: 일반 7일, 제재 30일. `pageIndex` / `curPage` 페이지네이션. `fsc.go.kr`만
  `curPage`.
- Gemini 2-tier: filter(`MODEL_FILTER_ID`) → analyze(`MODEL_ANALYZER_ID`,
  실패 시 `MODEL_ANALYZER_FALLBACK`). 키워드 safeguard로 score 보정.
- DB 저장 (`articles` 테이블) + Telegram 알림(`analysis_status == 'ANALYZED'`일 때만).
- Supabase `articles` 스키마: `agency`, `title`, `link`, `published_at`, `content`,
  `analysis_result`(JSON), `category`. **이번 라운드에서 변경 없음.**
- 환경변수 인터페이스: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ENV_TYPE`.
- 분석 결과 JSON 키: `risk_level`, `risk_score`, `summary`, `impact_analysis`,
  `action_items`, `pillars`, `risk_tags`, `analyzed_by`, `analysis_status`,
  `is_relevant`, `importance_score`, `filter_status`. 키 이름·구조 동일 유지.

## 3. 건드리지 않을 범위 (out of scope)

- **DB 스키마**: 이번 라운드에서 변경 0건. 인덱스/nullable 컬럼 추가는 제도상
  허용 범위로만 남겨두고, 실제 사용은 별도 task(MOEF 또는 성능)에서 한다.
- **`web/` 프론트엔드**: 전체 제외.
- **`config/agencies.json`** 의 데이터(URL/selector/keyword): 변경 금지. MOEF 소스
  교체는 별도 task.
- **`.github/workflows/*`**: 손대지 않음.
- **`scripts/debug/`**, 루트 dump 파일(`debug_*.md/.py`, `*.txt`,
  `agency_stats.json` 등), `docs/*.resolved.*` / 스크린샷: 정리 보류. 삭제·이동
  금지.
- **Gemini 프롬프트 본문**: 문장 내용 그대로 옮기기만. 의미 변경 금지.
- **Telegram 메시지 포맷**: 동일 유지.

## 4. 회귀 체크리스트

- [ ] `pip install -r requirements.txt` 통과.
- [ ] `python -c "from src.pipeline import Pipeline"` import 부작용 없이 통과
      (`.env` 없어도 import 자체는 성공해야 함).
- [ ] `python -c "from src.services.analyzer import HybridAnalyzer"` import만으로
      `genai.configure` / `logging.basicConfig` 가 호출되지 않음.
- [ ] `python src/main.py` 1사이클 정상 종료. 로그상 9개 agency 모두 처리되는지
      확인 (`.env` 채운 환경에서 수동 실행).
- [ ] 새 article 1건 이상 DB 저장 확인 (수동).
- [ ] 제재 중복 체크가 동일 케이스(같은 `examMgmtNo`+`emOpenSeq`)를 여전히
      걸러냄.
- [ ] Telegram 알림 포맷이 기존과 동일.
- [ ] 분석 결과 JSON 키 셋 동일.

## 5. 우선순위 (phase 순서)

1. 진단 + 모듈 경계 설계 문서화 (코드 변경 없음).
2. `config/` 정리 — settings 단일 진입점, `.env` 로더 일원화, agency 코드 enum/상수.
3. `src/db/client.py` lazy init — import 시 raise 제거. `pipeline.py`의 try/except
   import 제거.
4. `analyzer.py` 분해 — 프롬프트/모델 클라이언트/safeguard/결과 매핑 분리. 모듈
   import 사이드이펙트 제거.
5. `scraper.py` 분해 — HTTP 세션, 날짜 파서, 리스트 스크래퍼, 본문 스크래퍼,
   제재 스크래퍼 분리. agency별 페이지네이션 분기 strategy화.
6. `pipeline.py` 슬림화 — 단계별 함수 분리, 사이클 시작 시 dedup 캐시(`existing
   links` 1쿼리, `last_crawled` 1쿼리/agency).
7. 회귀 검증 phase — 빌드/import/회귀 체크리스트 수동 확인.

## 6. AC (전체 task 완료 기준)

- `pip install -r requirements.txt` 성공.
- `python -c "from src.pipeline import Pipeline"`, `from src.services.analyzer
  import HybridAnalyzer` 둘 다 사이드 이펙트 없이 통과.
- `python src/main.py` 1사이클 정상 종료, 9개 agency 처리 로그 확인.
- 회귀 체크리스트 전부 통과.
- agency 코드 문자열 리터럴 0건 (enum/상수만 사용).
- DB 스키마 diff 0건.
- `web/`, `config/agencies.json`, `.github/`, `scripts/`, 루트 dump 파일 diff 0건.

## 7. 권장 목표치 (강제 AC 아님)

`regression-report.md`에 결과를 기록만 하고, 미달이어도 phase 실패로 처리하지
않는다.

- `src/pipeline.py` < 180 LOC
- `src/collectors/` 의 단일 파일 < 200 LOC
- `src/services/analyzer/hybrid.py` < 200 LOC

## 8. 다음 라운드로 미루는 항목

- MOEF 소스 교체 (별도 task).
- 인덱스/컬럼 추가를 동반한 dedup/성능 개선 (별도 task).
- 프론트 `DashboardV2.tsx` 분해.
- `scripts/debug/`, 루트 dump, `docs/*.resolved.*` 정리/아카이브.
