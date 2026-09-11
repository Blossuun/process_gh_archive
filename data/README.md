# data/ — Phase 0 원본 실측

Phase 0 의 목적은 **파이프라인 설계에 쓸 수치 근거를 원본에서 직접 뽑는 것**이다.
분석이 목적이 아니므로 여기서 나온 값은 이후 Phase 에서 파서 버퍼, 파티션 크기,
Kafka 설정, 성능 목표를 정할 때 참조된다.

이 문서만 따라 하면 동일한 결과를 재현할 수 있다.

## 구성

    data/
    ├── README.md                  # 이 문서
    ├── download_gharchive.py      # GH Archive 원본 다운로드
    ├── measure_raw.py             # 날짜 단위 집계
    ├── measure_files.py           # 파일 단위 집계
    ├── gharchive/                 # 원본 .json.gz (추적 제외)
    │   └── YYYY-MM-DD-H.json.gz
    └── meta/
        ├── download_manifest.csv  # 다운로드 기록
        └── raw_file_stats.csv     # 파일 단위 통계

`ingest_log.db` 는 Phase 1 이후 적재 상태를 관리하는 파일로 Phase 0 산출물이 아니다.

원본 `.json.gz` 는 7.1GB 라 추적하지 않는다.
`meta/` 의 CSV 두 개는 아래 기준값의 근거이므로 추적한다.

## 대상 날짜

임의 선정한 4개 날짜의 24시간치, 총 96개 파일.

| 날짜 | 선정 의도 |
|---|---|
| 2020-08-12 | 초기 규모 |
| 2022-08-17 | 중간 규모 |
| 2024-08-14 | 최대 규모 + 부분 적재 사례 포함 |
| 2025-09-24 | 균일 감소 이후, payload 축소 이전 |

## 재현 절차

프로젝트 루트에서 실행한다.

### 1. 다운로드

```powershell
uv run data\download_gharchive.py --start 2020-08-12-0 --end 2020-08-12-23
uv run data\download_gharchive.py --start 2022-08-17-0 --end 2022-08-17-23
uv run data\download_gharchive.py --start 2024-08-14-0 --end 2024-08-14-23
uv run data\download_gharchive.py --start 2025-09-24-0 --end 2025-09-24-23
```

디스크 7.1GB, 소요 약 13분. 결과는 `meta/download_manifest.csv` 에 기록된다.

### 2. 파일 단위 집계

```powershell
uv run data\measure_files.py
```

`meta/raw_file_stats.csv` 생성. 소요 약 142초로 원본 54GB 를 전량 스트리밍한다.
진행 상황은 stderr 로 파일당 한 줄씩 출력되며, 파일마다 flush 하므로
중간에 끊겨도 그 시점까지는 CSV 에 남는다.

### 3. 날짜 단위 집계 (선택)

```powershell
uv run data\measure_raw.py
```

표준출력으로 날짜별 JSON 한 줄씩.
2 단계 결과를 날짜로 합치면 같은 값이 나오므로 교차 검증용이다.

## 산출물 스키마

### meta/download_manifest.csv

| 컬럼 | 내용 |
|---|---|
| `date`, `hour` | 대상 시각 (UTC) |
| `filename` | 파일명 |
| `status` | `ok` / 실패 사유 |
| `bytes` | 내려받은 gz 크기 |
| `attempts` | 시도 횟수 |
| `elapsed_sec` | 소요 시간 |
| `recorded_at` | 기록 시각 |

### meta/raw_file_stats.csv

| 컬럼 | 내용 |
|---|---|
| `date`, `hour`, `filename` | 대상 파일 |
| `gz_bytes` | 압축 크기 |
| `raw_bytes` | 해제 크기 |
| `events` | 이벤트(행) 수 |
| `max_line_bytes` | 가장 큰 단일 이벤트 크기 |
| `big_lines` | 1MB 초과 이벤트 수 |
| `empty_lines` | 개행뿐인 줄 수 |
| `elapsed_sec` | 읽기 소요 시간 |

## 기준값

재실행 시 아래와 일치해야 한다. 다르면 원본이 바뀌었거나 스크립트가 달라진 것이다.

| 날짜 | 이벤트 | gz | 해제 | 압축률 |
|---|---|---|---|---|
| 2020-08-12 | 2,453,420 | 1,238.8 MB | 8.74 GiB | 7.22× |
| 2022-08-17 | 3,675,976 | 1,813.4 MB | 13.78 GiB | 7.78× |
| 2024-08-14 | 4,679,055 | 2,231.3 MB | 16.33 GiB | 7.49× |
| 2025-09-24 | 3,815,767 | 1,965.5 MB | 14.20 GiB | 7.40× |

합계 96 파일 / gz 7.1GB / 해제 54GB / 이벤트 14,624,218 건.

### 도출된 설계 근거

| 값 | 실측 | 쓰이는 곳 |
|---|---|---|
| 압축률 | 7.2 ~ 7.8× | 임의 날짜 용량 추정 |
| 시간 파일 상한 | gz 123MB / 해제 920MB / 26만 건 | 처리 단위 상한 |
| 최대 단일 이벤트 | 1,887,999 B | 레코드 크기 제한 설정 |
| 1MB 초과 이벤트 | 1,462만 건 중 2건 | 상동 |
| 라인 크기 중앙값 / 상위 1% | 270KB / 1,085KB | 이상치 임계값 |
| 빈 줄 | 0건 | 줄당 이벤트 하나 — 파서 단순화 |
| gz 크기 ↔ 처리 시간 상관 | 0.983 | 작업 배분 키 (파일 안 열고 판단 가능) |
| 읽기 성능 | 378 MB/s (gzip 해제 포함) | 성능 기준선 |

## 알려진 이상

### 2024-08-14-23 — 부분 적재

**489건.** 인접 시간대 기준 예상치의 0.35% 다.
파일 존재, gzip 정상, 파싱 정상이라 **행 수 임계값으로만 검출된다.**
BigQuery `githubarchive.day` 행 수도 로컬과 일치하므로 원본 수준 결손이며
다운스트림에서 보정되지 않는다. 품질 게이팅 검증용 실데이터로 사용한다.

### 2025-09-24 — max_line 반복

24시간 중 14개 시간의 `max_line_bytes` 가 270KB 로 동일하다.
다른 3개 날짜에는 이런 패턴이 없다. 원인 미확인.

### 파일명 정렬

`2024-08-14-10` 이 `2024-08-14-2` 보다 문자열 정렬에서 앞선다.
파일 목록을 다룰 때는 `(date, hour)` 를 파싱해 **`hour` 를 int 로 정렬**해야 한다.

```python
PAT = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{1,2})\.json\.gz$")
key = lambda p: (m.group(1), int(m.group(2)))
```

집계 결과 자체는 순서와 무관하므로 위 기준값에는 영향이 없다.

## BigQuery 대조

[`../data_analysis/BQ_EDA/query/table_inventory.sql`](../data_analysis/BQ_EDA/query/table_inventory.sql)
결과와 대조한 내용. 조사 전체는
[`../data_analysis/BQ_EDA/`](../data_analysis/BQ_EDA/) 참조.

- **행 수**: 4개 날짜 모두 완전 일치 → 이벤트 수는 BQ 값을 그대로 사용 가능
- **용량**: 로컬이 3.6 ~ 4.4% 크다. 로컬은 JSON 텍스트 바이트(개행 포함),
  BQ 는 컬럼 타입별 논리 바이트라 측정 기준이 다르다.
  절대 용량 계획은 로컬 실측 기준으로 잡는다.