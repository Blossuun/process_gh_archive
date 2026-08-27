# BQ_EDA — GH Archive 필드 탐색

GH Archive 파이프라인에서 **어떤 필드를 남길지 결정**하기 위한 탐색 단계입니다.
BigQuery는 이 판단 근거를 만드는 데만 사용하며, 파이프라인 본체는 이 디렉터리에 의존하지 않습니다.

## 사전 요구사항

- Google 계정
- BigQuery 샌드박스 프로젝트 (결제 계정 불필요)
- gcloud CLI
- uv

BigQuery 샌드박스는 월 1TB 스캔, 10GB 스토리지가 무료이며 결제 계정을 연결하지 않습니다.
따라서 이 디렉터리의 쿼리를 실행해도 요금이 청구될 수 없습니다.
한도를 초과하면 쿼리가 거부될 뿐입니다.

## 1. 샌드박스 프로젝트 생성

1. https://console.cloud.google.com/bigquery 접속
2. Google 계정으로 로그인, 약관 동의
3. `프로젝트 만들기` → 이름 입력 → 생성
4. 생성된 **프로젝트 ID**를 기록 (이후 `YOUR_PROJECT_ID`로 표기)

## 2. 도구 설치

### Windows (PowerShell)

```powershell
winget install -e --id Google.CloudSDK
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 **PowerShell 창을 새로 열어야** PATH가 반영됩니다.

winget이 없다면 설치 프로그램을 직접 받습니다.

```powershell
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe
```

### WSL2 / Linux

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates gnupg curl
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
  | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
  | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update
sudo apt-get install -y google-cloud-cli

curl -LsSf https://astral.sh/uv/install.sh | sh
```

### macOS

```bash
brew install --cask google-cloud-sdk
brew install uv
```

## 3. 인증

```
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

브라우저가 열리면 계정을 선택하고 권한을 허용합니다.
WSL2에서 브라우저가 자동으로 열리지 않으면, 출력된 URL을 Windows 브라우저에 붙여넣고
받은 인증 코드를 터미널에 입력합니다.

두 번째 명령을 생략하면 API 호출마다 quota project 경고가 발생합니다.

서비스 계정 키 파일은 필요하지 않습니다. 개인 계정 ADC로 충분하며,
키 파일이 저장소에 커밋되는 사고도 방지됩니다.

## 4. 실행

```
uv run run_query.py query/table_inventory.sql --dry-run   # 예상 스캔량만 확인
uv run run_query.py query/table_inventory.sql             # 실행
```

- 결과는 기본적으로 `results/<쿼리파일명>.json`에 저장됩니다.
- 실행 이력과 비용은 `query_log.csv`에 자동으로 누적됩니다.
- `-o` 로 출력 경로를, `--max-bytes` 로 스캔 상한을 변경할 수 있습니다.

러너는 항상 **dry run → 상한 검사 → 실행** 순으로 동작합니다.
예상 스캔량이 상한(기본 2GB)을 넘으면 실행하지 않고 종료 코드 2로 중단합니다.

## 재현성

- `query/*.sql`이 유일한 원본입니다. 쿼리는 파이썬 코드에 문자열로 박아 넣지 않습니다.
- 조회 대상은 특정 날짜의 `githubarchive.day.YYYYMMDD` 테이블로 고정합니다.
  과거 날짜 테이블은 갱신되지 않으므로, 같은 쿼리는 언제 실행해도 같은 결과를 냅니다.
  단 `yesterday` 뷰와 당일 테이블은 갱신 중이므로 사용하지 않습니다.
- `results/`와 `query_log.csv`를 저장소에 함께 커밋합니다.
  다른 사람은 자신의 결과와 커밋된 결과를 비교해 재현 여부를 직접 확인할 수 있습니다.
- 실행자마다 프로젝트 ID가 다르지만, 쿼리는 공개 데이터셋만 참조하므로
  프로젝트 ID가 쿼리문에 등장하지 않습니다. 따라서 쿼리 파일 수정 없이 그대로 재현됩니다.

## 디렉터리

```
BQ_EDA/
├── README.md
├── run_query.py       실행 러너
├── query/             쿼리 원본 (.sql)
├── results/           쿼리 결과 (.json)
└── query_log.csv      실행 이력과 비용
```