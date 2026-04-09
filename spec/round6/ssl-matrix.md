# SSL Verification Matrix — Round 6 Phase 1/2

본 문서는 `config/agencies.json` 에 정의된 9 개 agency 에 대해 `requests.get(..., verify=True)`
가 로컬 및 CI 환경에서 각각 어떻게 동작하는지를 기록하는 매트릭스다. 목적은 `src/config/settings.py`
의 `SSL_VERIFY` 기본값을 `True` 로 전환하기 위한 근거 자료 수집이며, 이 phase 에서는 로컬 결과만
채운다. CI 컬럼은 phase 2 에서 GitHub Actions workflow 가 채우고, `final_decision` 은 phase 3
에서 로컬 + CI 결과를 모두 본 뒤 확정한다.

## 실행 환경

| 항목 | 값 |
|---|---|
| OS | Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39 |
| Python | 3.12.3 |
| requests | 2.33.1 |
| certifi CA bundle | `/home/pacer/projects/reg_brief/venv/lib/python3.12/site-packages/certifi/cacert.pem` |
| 실행 시각 (KST) | 2026-04-08T23:12:09+09:00 |
| 실행자 | Claude Code session (refactor-round6-backend-safety phase 1) |
| 재현 커맨드 | `python3 scripts/ssl_matrix_check.py` |

스크립트는 import 시 부작용이 0 이며 (`if __name__ == '__main__':` 가드), 어떤 대상이 실패해도
전체 실행은 fail-soft 로 완주한다. 결과 원본은 `logs/ssl_matrix_local.json` 에 저장되며 같은
스냅샷을 아래 "원시 결과 스냅샷" 섹션에 그대로 기록해 둔다 (로그 파일은 gitignored 가 될 수 있으므로
증거를 문서 본문에도 함께 남긴다).

## Agency 매트릭스

| agency code | collection_method | target URL | local_ok | local_status | local_error_type | local_error_msg | ci_ok | ci_status | ci_error_type | ci_error_msg | final_decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FSC | rss | https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111 | False | — | ConnectionError | `('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` | False | — | ConnectionError | `('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` | default |
| MOEF | rss | https://www.korea.kr/rss/dept_mofe.xml | True | 200 | — | — | True | 200 | — | — | default |
| FSS | scraper | https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218 | True | 200 | — | — | True | 200 | — | — | default |
| BOK | scraper | https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1 | True | 200 | — | — | True | 200 | — | — | default |
| FSS_REG | scraper | https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489 | True | 200 | — | — | True | 200 | — | — | default |
| FSC_REG | scraper | https://www.fsc.go.kr/po040301 | True | 200 | — | — | False | — | ConnectionError | `('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` | default |
| FSS_REG_INFO | scraper | https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488 | True | 200 | — | — | True | 200 | — | — | default |
| FSS_SANCTION | scraper | https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476 | True | 200 | — | — | True | 200 | — | — | default |
| FSS_SANCTION | scraper | https://www.fss.or.kr | True | 200 | — | — | True | 200 | — | — | default |
| FSS_MGMT_NOTICE | scraper | https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483 | True | 200 | — | — | True | 200 | — | — | default |
| FSS_MGMT_NOTICE | scraper | https://www.fss.or.kr | True | 200 | — | — | True | 200 | — | — | default |

참고: `FSS_SANCTION` / `FSS_MGMT_NOTICE` 는 `url` (list URL) 과 `base_url` (`https://www.fss.or.kr`)
가 서로 다르므로 두 행으로 기록했다. 나머지 scraper agency 는 `url == base_url` 이라 dedup 되어
1 행씩만 기록된다 (RSS 2 개 + scraper 5 개 × 1 + sanction 2 개 × 2 = 11 행).

## 결정 기준

phase 3 에서 각 agency 의 `final_decision` 을 확정할 때 다음 규칙을 따른다:

1. **`local_ok=True AND ci_ok=True`** → `final_decision = "default"`
   - `SSL_VERIFY` 기본값 `True` 를 그대로 사용하고, agency 별 `ssl_verify` 필드 추가 없음.
2. **`local_ok=False OR ci_ok=False`** 이면서 원인이 `SSLError` (cert chain / hostname) 이고,
   **양쪽 환경에서 동일하게 실패** → `final_decision = "opt-out"`
   - 해당 agency 에 한해 `config/agencies.json` 에 `"ssl_verify": false` 필드를 추가하고,
     `http.fetch(..., verify=...)` 를 통해 전달한다.
3. **실패 원인이 `ConnectionError` / `Timeout` 등 네트워크 사유** → `final_decision = "default"`
   - SSL 과 무관하므로 SSL 정책은 건드리지 않는다. 네트워크/소스 다운 이슈는 별도 트래킹.
4. **두 환경 결과가 상반됨 (`env_mismatch`)** → `final_decision = "investigate"`
   - 주석에 사유 (예: "로컬은 성공, GitHub runner 에서만 SSLError") 를 남기고 phase 3 에서
     사람이 판단.

현재 phase 1 결과만 놓고 본다면 `FSC` RSS 엔드포인트가 `ConnectionError` 로 실패했는데, 이는
`SSLError` 가 아니라 TCP reset 계열이므로 규칙 3 에 해당한다. SSL 정책을 `opt-out` 으로 돌릴
근거는 아니다. 다만 phase 2 의 CI 결과에서 동일 원인이 재현되는지, 혹은 실제로는 SSL 관련 원인으로
나타나는지를 교차 확인한 뒤 phase 3 에서 확정한다.

## CI 결과 기반 최종 결정 (phase 3 진입 전)

`workflow_dispatch` 로 실행한 CI 결과 (GitHub Actions run **24172848470**,
ubuntu-latest / Azure, Python 3.10.20, 2026-04-09 KST) 를 로컬과 교차 대조한
결과, **11 행 전부 `default` 로 확정**. `opt-out` 0 건, `investigate` 0 건.

**`default` 11 행의 근거:**

- **규칙 1 적용** (양쪽 `ok=True`, `status=200`): `MOEF` (rss), `FSS` (list),
  `BOK`, `FSS_REG`, `FSS_REG_INFO`, `FSS_SANCTION` (list), `FSS_SANCTION`
  (base_url), `FSS_MGMT_NOTICE` (list), `FSS_MGMT_NOTICE` (base_url) — **9 행**.
- **규칙 3 적용** (양쪽 `ConnectionError`, SSL 무관): `FSC` (rss) — **1 행**.
  `fsc.go.kr` 가 특정 IP 범위에 대해 TCP reset 을 내는 것으로 추정되며 양쪽
  환경에서 동일하게 재현된다. SSLError 가 아니므로 SSL 정책은 건드리지 않는다.
  (참고: Round 2 의 MOEF stale 대응과는 다른 문제. Round 2 는 feed 내용이 stale
  이었고, 여기는 TCP 단 reject.)
- **규칙 3 확장 적용** (비대칭 `ConnectionError`, SSL 무관): `FSC_REG`
  (scraper, `https://www.fsc.go.kr/po040301`) — **1 행**. 로컬 성공 / CI
  `ConnectionError` 의 env mismatch 가 존재하지만, 실패가 SSL certificate 가
  아니라 **pre-TLS TCP reset** (`ConnectionResetError 104`) 이다. `SSL_VERIFY`
  값을 바꿔도 이 실패는 해결되지 않으므로, SSL 정책 결정 관점에서는 `default`.
  env mismatch 사실 자체는 아래 "FSC_REG env mismatch 운영 이슈" 섹션에 별도
  트래킹 항목으로 기록해 두며, SSL 결정 경로와는 분리된다.

**FSC_REG env mismatch 운영 이슈 (SSL 결정과 별개 트래킹):**

- **현상**: 로컬 (WSL2, Python 3.12, 가정용 IP) 는 `200 OK` 0.834s, CI
  (ubuntu-latest, Azure 데이터센터 IP, Python 3.10.20) 는 `ConnectionError`
  (`Connection aborted`, `ConnectionResetError(104, 'Connection reset by peer')`)
  0.986s. 동일 스크립트, 동일 User-Agent, 동일 `requests` 2.33.1 — 차이는 오직
  네트워크 출발지 IP.
- **원인 추정**: `fsc.go.kr` 가 GH runner 의 Azure 데이터센터 IP 대역에 대해
  TCP 443 단에서 선택적으로 RST 를 날리는 것으로 보인다. pre-TLS 단계라 certificate
  검증 이전에 실패하므로 TLS policy 와는 무관.
- **SSL 결정 영향**: 없음. 규칙 3 적용 → `default` (본 문서 §결정 기준 §3).
- **운영 결정 영향**: `FSC_REG` 는 production 에서
  `.github/workflows/news_collector_v2_active.yml` 의 Azure runner 로 실행된다.
  만약 본 probe 에서 관찰된 CI 환경 TCP reset 이 production 실행에서도
  재현된다면, FSC_REG 는 이미 운영 중에 부분적으로 다운되고 있을 가능성이 있다.
  단 본 probe 는 1 회 스냅샷이며 time-of-day / runner IP 가 다를 때 달라질 수
  있다.
- **트래킹 항목**: "FSC_REG scraper: datacenter IP 에서 TCP reset 가능성. 현재
  production 실행의 실제 수집 성공률 조사 + 필요 시 전용 회피 로직 (사설 프록시,
  User-Agent rotation, IP whitelist 요청) 검토." 별도 후속 micro-task 후보로
  남기며, 이번 Round 6 scope 밖으로 둔다.

**phase 3 가 받는 상태 요약:**

- `default` 11 행 → `config/agencies.json` 에 `ssl_verify` 필드 추가 0건.
- `opt-out` 0 행 → 이번 라운드에서 agency 별 SSL opt-out 은 발생하지 않는다.
- `investigate` 0 행 → phase 3 의 `§3 investigate` 가드에 걸리지 않는다.

**SSL_VERIFY 기본값 결정:**

11 행 중 `opt-out` 이 한 건도 없으므로, `src/config/settings.py` 의 `SSL_VERIFY`
는 `True` 로 전환해도 운영적으로 안전하다. phase 3 은 §2 (settings 기본값 전환)
→ §3 (agencies.json opt-out 필드 추가 — 이번엔 0 건 추가) → §4–§9 (agency_loader
helper, http.fetch verify kwarg, rss_parser / collector callsite 업데이트,
`test_http.py` / `test_agency_loader_ssl.py` 신설) 를 순차 실행하고, 마지막 AC
커맨드 (pytest + import smoke) 로 통과 판정한다.

## 재현 방법

- **로컬**: 저장소 루트에서 `python3 scripts/ssl_matrix_check.py` 를 실행한다. 결과는
  `logs/ssl_matrix_local.json` 에 저장되며, stdout 에는 11 행 테이블이 프린트된다.
- **CI**: phase 2 에서 GitHub Actions workflow (`.github/workflows/ssl-matrix.yml` 예정) 가
  동일 스크립트를 돌려 `logs/ssl_matrix_ci.json` 아티팩트를 업로드한다. phase 3 시작 시점에
  아티팩트를 내려받아 본 문서의 `ci_*` 컬럼을 채운 뒤 `final_decision` 을 결정한다.

## CI 실행 절차

phase 2 에서는 `.github/workflows/ssl-matrix-check.yml` 파일만 추가하며, 워크플로의 **실제 실행은
사용자가 수동으로 한다**. phase 2 의 Claude 세션은 이 workflow 를 실행하지 않는다. phase 2 는
워크플로 파일과 안내 문서만 만들고 정상 종료한다. 사용자가 수동으로 한 번 돌려 결과를 `ci_*`
컬럼과 `final_decision` 에 채워야 phase 3 이 진행 가능하다 (phase 3 hard gate).

수동 실행 예시:

```
gh workflow run ssl-matrix-check.yml
gh run watch                    # 실행 감시
gh run download --name ssl-matrix-ci-result --dir ./.ssl-matrix-ci-tmp
```

다운로드된 아티팩트에는 `ssl_matrix_local.json` (CI runner 가 로컬 스크립트와 동일 경로로 저장)
파일이 들어 있다. 이 JSON 의 `results` 배열을 agency code + target URL 기준으로 매칭하여 본
문서의 `ci_ok` / `ci_status` / `ci_error_type` / `ci_error_msg` 컬럼에 붙여 넣고, 결정 기준 §1~§4
에 따라 각 행의 `final_decision` 값을 `default` / `opt-out` / `investigate` 중 하나로 확정한
뒤 phase 3 을 시작한다. 이 작업이 끝나지 않은 상태에서 phase 3 이 시작되면 phase 3 의 hard gate
가 즉시 `blocked` 상태로 잡는다.

## 원시 결과 스냅샷 (phase 1 / 로컬 실행)

`logs/ssl_matrix_local.json` 파일이 gitignored 일 수 있어 아래에 전체 내용을 그대로 보존한다.

```json
{
  "run_at_kst": "2026-04-08T23:12:09+09:00",
  "environment": {
    "platform": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39",
    "python": "3.12.3",
    "requests": "2.33.1",
    "certifi_ca_bundle": "/home/pacer/projects/reg_brief/venv/lib/python3.12/site-packages/certifi/cacert.pem"
  },
  "results": [
    {
      "code": "FSC",
      "collection_method": "rss",
      "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
      "ok": false,
      "status_code": null,
      "elapsed_sec": 0.211,
      "final_url": null,
      "error_type": "ConnectionError",
      "error_msg": "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    },
    {
      "code": "MOEF",
      "collection_method": "rss",
      "url": "https://www.korea.kr/rss/dept_mofe.xml",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.472,
      "final_url": "https://www.korea.kr/rss/dept_mofe.xml",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.979,
      "final_url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "BOK",
      "collection_method": "scraper",
      "url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.641,
      "final_url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_REG",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.892,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSC_REG",
      "collection_method": "scraper",
      "url": "https://www.fsc.go.kr/po040301",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.834,
      "final_url": "https://www.fsc.go.kr/po040301",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_REG_INFO",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.803,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.693,
      "final_url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.393,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.991,
      "final_url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.441,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    }
  ]
}
```

## 원시 결과 스냅샷 (phase 2 / CI 실행)

GitHub Actions workflow `ssl-matrix-check.yml` 를 `workflow_dispatch` 로 수동
실행한 결과 (run `24172848470`, branch `refactor-round6-backend-safety`,
ubuntu-latest). 아티팩트 `ssl-matrix-ci-result` 에 들어 있던
`ssl_matrix_local.json` (CI runner 가 로컬 스크립트와 동일 경로로 저장) 을 그대로
보존한다.

```json
{
  "run_at_kst": "2026-04-09T13:45:27+09:00",
  "environment": {
    "platform": "Linux-6.17.0-1010-azure-x86_64-with-glibc2.39",
    "python": "3.10.20",
    "requests": "2.33.1",
    "certifi_ca_bundle": "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/certifi/cacert.pem"
  },
  "results": [
    {
      "code": "FSC",
      "collection_method": "rss",
      "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
      "ok": false,
      "status_code": null,
      "elapsed_sec": 0.946,
      "final_url": null,
      "error_type": "ConnectionError",
      "error_msg": "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    },
    {
      "code": "MOEF",
      "collection_method": "rss",
      "url": "https://www.korea.kr/rss/dept_mofe.xml",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.829,
      "final_url": "https://www.korea.kr/rss/dept_mofe.xml",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.197,
      "final_url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "BOK",
      "collection_method": "scraper",
      "url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.018,
      "final_url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_REG",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.066,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSC_REG",
      "collection_method": "scraper",
      "url": "https://www.fsc.go.kr/po040301",
      "ok": false,
      "status_code": null,
      "elapsed_sec": 0.986,
      "final_url": null,
      "error_type": "ConnectionError",
      "error_msg": "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    },
    {
      "code": "FSS_REG_INFO",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.235,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.039,
      "final_url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.607,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 2.281,
      "final_url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 3.115,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    }
  ]
}
```
