# BQ_EDA — GH Archive 필드 탐색

GH Archive 파이프라인에서 **어떤 필드를 남길지 결정**하기 위한 탐색 단계입니다.
BigQuery는 이 판단 근거를 만드는 데만 사용하며, 파이프라인 본체는 이 디렉터리에 의존하지 않습니다.

조사는 종료됐습니다. 남은 작업은 원본 `.json.gz` 의 용량 측정 하나입니다.

## 결과물

| 파일 | 내용 |
|---|---|
| `analysis/findings.md` | 무엇을 알아냈고 무엇을 정했는가. **여기부터 읽을 것** |
| `analysis/field_reference.md` | 필드에 무엇이 있고 무엇에 쓰는지. 조회용 |
| `analysis/provenance.md` | 쿼리·스크립트별 산출물과 거기서 알아낸 것 |
| `analysis/table_inventory_report.md` | 결측·이상일·볼륨 추이 (생성물) |
| `analysis/daily_volume.csv` | 3,702일의 적재 이상 여부 (생성물, 커밋하지 않음) |

## 사전 요구사항

- Google 계정
- BigQuery 샌드박스 프로젝트 (결제 계정 불필요)
- gcloud CLI, uv

BigQuery 샌드박스는 월 1TB 스캔이 무료이며 결제 계정을 연결하지 않습니다.
따라서 이 디렉터리의 쿼리를 실행해도 요금이 청구될 수 없습니다.
한도를 초과하면 쿼리가 거부될 뿐입니다.

## 설치

### Windows (PowerShell)

```powershell
winget install -e --id Google.CloudSDK
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 **PowerShell 창을 새로 열어야** PATH가 반영됩니다.

### WSL2 / Linux

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates gnupg curl
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
  | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
  | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update && sudo apt-get install -y google-cloud-cli
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### macOS

```bash
brew install --cask google-cloud-sdk
brew install uv
```

## 인증

```
gcloud auth application-default login
```

WSL2에서 브라우저가 자동으로 열리지 않으면 출력된 URL을 브라우저에 붙여넣고
받은 인증 코드를 터미널에 입력합니다.

프로젝트 ID는 `--project` 옵션, `GOOGLE_CLOUD_PROJECT` 환경변수,
`.env` 파일, ADC 의 `quota_project_id` 순으로 결정됩니다.
`.env.example` 을 `.env` 로 복사해 프로젝트 ID만 채우는 방식이 가장 간단합니다.
`.env` 는 git-ignored 이므로 저장소에는 `.env.example` 만 남습니다.

## 스크립트

### run_query.py

`.sql` 파일 하나를 실행하고 비용을 기록합니다.

```
uv run run_query.py query/table_inventory.sql --dry-run
uv run run_query.py query/table_inventory.sql
uv run run_query.py query/payload_keys_before.sql --max-bytes 15000000000
```

항상 **dry run → 상한 검사 → 실행** 순으로 동작합니다. 예상 스캔량이
상한(기본 2GB)을 넘으면 실행하지 않고 종료합니다. 결과는
`results/<쿼리파일명>.json` 에, 이력과 비용은 `query_log.csv` 에 쌓입니다.

주의할 점 두 가지입니다.

- `TABLESAMPLE` 을 쓴 쿼리에서는 dry run 추정치를 믿을 수 없습니다.
  추정은 표본 비율만큼 줄지만 실행 시에는 전체를 읽으려 합니다.
- 상한 초과 시 실제 필요량을 알려주고 **과금 없이** 실패하므로,
  비용을 미리 알아내는 수단으로도 쓸 수 있습니다.

### fetch_sample_rows.py

원본 행 전체를 **과금 없이** 가져옵니다.

```
uv run fetch_sample_rows.py githubarchive.day.20250924 githubarchive.day.20251112
```

`tabledata.list` API를 사용합니다. 쿼리 잡을 만들지 않으므로 스캔 바이트가 0 입니다.
`payload` 같은 무거운 컬럼을 통째로 읽어도 할당량을 소모하지 않습니다.
SQL 로 같은 일을 하면 하루치가 12.6GB 입니다.

행은 무작위가 아니라 저장 순서대로 읽힙니다. 구조 파악용이지 통계용이 아닙니다.

### analyze_inventory.py

```
uv run analyze_inventory.py --since 20160701
```

`results/table_inventory.json` 을 읽어 `analysis/` 에 보고서와 CSV 를 만듭니다.
BigQuery 를 다시 부르지 않으므로 `--since`, `--threshold`, `--window`, `--ratio`
를 바꿔가며 몇 번을 돌려도 할당량을 쓰지 않습니다.

`--since 20160701` 은 필수에 가깝습니다. 그 이전 테이블은 2016년 6월에
일괄 마이그레이션된 것이라 일일 적재분과 성격이 다릅니다.

## 전체 재현

아래를 순서대로 실행하면 `results/` 와 `analysis/` 가 처음부터 다시 만들어집니다.
BigQuery 사용량은 **총 19.64 GB**, 월 무료 한도 1TB 의 2% 입니다.
아래 숫자는 `query_log.csv` 에 기록된 실제 청구량입니다.

```
uv run run_query.py query/table_inventory.sql                                    #      0 B
uv run run_query.py query/schema_signature.sql                                   #   10 MB
uv run run_query.py query/hourly_completeness.sql                                #  304 MB
uv run run_query.py query/other_column_stats.sql --max-bytes 500000000           #  305 MB
uv run run_query.py query/type_trend_quarterly.sql --max-bytes 2000000000        # 1.55 GB
uv run run_query.py query/type_trend_monthly.sql --max-bytes 2500000000          # 1.76 GB
uv run run_query.py query/payload_keys_after.sql --max-bytes 6000000000          # 3.10 GB
uv run run_query.py query/payload_keys_before.sql --max-bytes 15000000000        # 12.63 GB

uv run fetch_sample_rows.py githubarchive.day.20250924 githubarchive.day.20251112  # 0 B

uv run analyze_inventory.py --since 20160701
```

`results/` 와 `analysis/` 의 데이터 파일(`.json`, `.csv`)은 저장소에 커밋하지 않습니다.
의미 있는 결과는 `analysis/` 의 문서에 기록되어 있고, 데이터가 필요하면 위 절차로 다시 만듭니다.

`--max-bytes` 를 명시한 쿼리는 기본 상한 2GB 를 넘습니다. 기본값을 코드에서 올리지 않는 이유는,
평소에는 2GB 에서 막히는 편이 안전하고 비싼 쿼리만 그때마다 의식적으로 허용하는 편이 낫기 때문입니다.

`analyze_inventory.py` 의 `--since 20160701` 은 사실상 필수입니다. 그 이전 테이블은
2016년 6월에 일괄 마이그레이션된 것이라 일일 적재분과 성격이 다릅니다.

## 재현성

- `query/*.sql` 이 유일한 원본입니다. 쿼리를 파이썬 코드에 문자열로 넣지 않습니다.
- 조회 대상은 특정 날짜의 `githubarchive.day.YYYYMMDD` 로 고정합니다.
  과거 날짜 테이블은 갱신되지 않으므로 같은 쿼리는 언제 실행해도 같은 결과를 냅니다.
- `results/`, `analysis/`, `query_log.csv` 를 저장소에 함께 커밋합니다.
  다른 사람은 자신의 결과와 비교해 재현 여부를 직접 확인할 수 있습니다.
- 쿼리는 공개 데이터셋만 참조하므로 프로젝트 ID가 쿼리문에 등장하지 않습니다.
  따라서 쿼리 파일 수정 없이 그대로 재현됩니다.

## 디렉터리

```
BQ_EDA/
├── README.md
├── .env                프로젝트 ID (git-ignored)
├── .env.example
├── .gitignore
├── run_query.py        쿼리 실행 러너
├── fetch_sample_rows.py  원본 행 수집 (과금 없음)
├── analyze_inventory.py  인벤토리 분석 (표준 라이브러리만)
├── query/              쿼리 원본 (.sql)
├── results/            쿼리 결과 (.json)
├── analysis/           분석 문서와 산출물
└── query_log.csv       실행 이력과 비용
```