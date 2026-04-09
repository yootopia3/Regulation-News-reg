# Phase 2: magic-number-docstrings

## 사전 준비

먼저 아래 문서를 읽어 설계 의도를 파악하라:

- `/home/pacer/projects/reg_brief/spec/refactor-round6-roadmap.md` (§3.3 N3, §7.3, §8.3 phase 2)
- `/home/pacer/projects/reg_brief/CLAUDE.md`

그리고 아래 핵심 소스 파일을 직접 읽어 현재 동작을 파악하라. 리팩토링이라면 source-first다:

- `/home/pacer/projects/reg_brief/src/collectors/sanction_scraper.py` — 특히:
  - L21 `MAX_PAGES = 10`
  - L22 `CUTOFF_DAYS = 30`
  - 위 두 상수가 `fetch_sanction_items` 안에서 어떻게 쓰이는지 확인.
- `/home/pacer/projects/reg_brief/spec/moef-source-round2.md` (sanction 스크래핑 정책 배경)
- `/home/pacer/projects/reg_brief/spec/refactor-round1.md` (sanction cutoff 정책 — "제재 30일")

이전 phase의 작업물도 확인하라:

- task 10 phase 1 (deprecated 상수 제거).

문서보다 코드가 우선이다. 둘이 어긋나면 코드를 신뢰하고, 의문점은 작업 중 기록하라.

## 작업 내용

목표: `MAX_PAGES`, `CUTOFF_DAYS` 상수 위에 "왜 이 값인지" 를 1–2 줄 주석으로 추가. **값 변경 금지**.

1. **`src/collectors/sanction_scraper.py` 수정**:
   - 변경 전:
     ```python
     MAX_PAGES = 10
     CUTOFF_DAYS = 30
     ```
   - 변경 후:
     ```python
     # Hard ceiling on sanction list pagination. FSS 의 검사결과 제재 / 경영유의사항
     # 페이지는 한 번의 search window (sdate~edate, default 30 일) 안에서
     # 보통 5~10 페이지를 넘지 않는다. 10 으로 캡 두어 사이트 레이아웃 변경이나
     # 필터 누락으로 인한 무한 루프를 차단한다 (방어적 ceiling).
     MAX_PAGES = 10

     # Lookback window for the sanction search query (sdate=today-CUTOFF_DAYS).
     # 제재 공시는 저빈도 + 백필이 잦아서 일반 보도자료(7 일) 보다 길게 본다.
     # 30 일은 새 게시물을 놓치지 않으면서 전체 아카이브를 매번 다시 긁지 않을
     # 수 있는 minimum 윈도다 (round 1 §2 회귀 정책과 일치).
     CUTOFF_DAYS = 30
     ```
   - **상수 값 변경 금지**. `MAX_PAGES = 10`, `CUTOFF_DAYS = 30` 그대로.
   - 다른 로직 변경 금지. 이 phase 는 주석 추가뿐이다.

2. **회귀 검증**: 기존 `tests/unit/collectors/test_sanction_scraper.py` 가 통과해야 한다.

## Acceptance Criteria

```bash
# 1) 상수 값이 변경되지 않았는가
grep -q "^MAX_PAGES = 10$" src/collectors/sanction_scraper.py
grep -q "^CUTOFF_DAYS = 30$" src/collectors/sanction_scraper.py

# 2) 주석이 추가되었는가 (각 상수 직전 줄에 #)
python3 - <<'PY'
with open('src/collectors/sanction_scraper.py') as f:
    lines = f.readlines()

def has_comment_above(target_line):
    for i, line in enumerate(lines):
        if line.strip() == target_line:
            # 바로 위 라인이 주석인지 확인
            if i > 0 and lines[i-1].strip().startswith('#'):
                return True
    return False

assert has_comment_above("MAX_PAGES = 10"), "MAX_PAGES needs comment above"
assert has_comment_above("CUTOFF_DAYS = 30"), "CUTOFF_DAYS needs comment above"
print("both constants have docstring comments")
PY

# 3) 기존 sanction_scraper 테스트 무회귀
python3 -m pytest tests/unit/collectors/test_sanction_scraper.py -q

# 4) 전체 단위 테스트 무회귀
python3 -m pytest tests/unit -q

# 5) import smoke
python3 -c "from src.collectors.sanction_scraper import fetch_sanction_items, MAX_PAGES, CUTOFF_DAYS; assert MAX_PAGES == 10 and CUTOFF_DAYS == 30"
```

## AC 검증 방법

위 AC 커맨드를 실행하라. 모두 통과하면 `/tasks/10-round8-hardening/index.json`의 phase 2 status를 `"completed"`로 변경하라.
수정 3회 이상 시도해도 실패하면 status를 `"error"`로 변경하고, 에러 내용을 index.json의 해당 phase에 `"error_message"` 필드로 기록하라.

## 주의사항

- **상수 값 절대 변경 금지**. 10 → 11, 30 → 28 같은 미세 조정도 금지.
- 주석 외 코드 변경 금지. import / 함수 / 클래스 손대지 마라.
- 주석 톤은 한국어 (다른 sanction_scraper 의 docstring 과 일관). 영어 주석을 섞지 말 것.
- 주석은 **상수 위쪽** 에 둔다. inline 주석 (`MAX_PAGES = 10  # ...`) 은 금지 — 길어지면 가독성 떨어짐.
- 다른 magic number (예: `random.uniform(1.0, 2.0)`, `random.uniform(0.5, 1.0)` 의 sleep 윈도우, `len(items) < 5` 의 5 등) 는 이 phase 에서 건드리지 마라. scope 최소화.
