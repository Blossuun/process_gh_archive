# Silver 테이블 설계와 구축 계획

원본 JSON 이벤트를 질의 가능한 정형 테이블로 평탄화하는 설계.

근거는 `data_analysis/BQ_EDA/analysis/field_reference.md` 와 `findings.md`.

---

## 계층 구조

```
원본 .json.gz          시간당 1파일, 중첩 JSON
    ↓  다운로드·검증
bronze                 원본 그대로. 파싱 최소화, 재처리 대비
    ↓  평탄화·타입 지정·중복 제거
silver                 질의 가능한 정형 테이블
    ↓  집계
gold                   부 목표 A·B 의 산출물
```

bronze 를 두는 이유는 재처리 때문이다. silver 설계가 바뀌어도 원본을 다시 받지 않고 bronze 에서 다시 만들면 된다.

---

## 테이블 3개

타입 16종을 전부 개별 테이블로 만들지 않는다. **목표에 쓰이는 것만** 만들고, 나머지는 `silver_events` 의 행으로만 남긴다.

### `silver_events` — 모든 이벤트의 공통 축

전 기간, 전 타입. 목표 2 계열 분석은 이 테이블 하나로 끝난다.

| 컬럼 | 타입 | 출처 | 비고 |
|---|---|---|---|
| `event_id` | STRING | `id` | **중복 제거 키** |
| `event_type` | STRING | `type` | |
| `created_at` | TIMESTAMP | `created_at` | UTC |
| `event_date` | DATE | `created_at` 파생 | **파티션 키** |
| `repo_id` | BIGINT | `repo.id` | **저장소 추적 기준.** 이름 변경에 불변 |
| `repo_name` | STRING | `repo.name` | `owner/repo` |
| `actor_id` | BIGINT | `actor.id` | |
| `actor_login` | STRING | `actor.login` | |
| `org_id` | BIGINT | `org.id` | 개인 저장소는 null |
| `org_login` | STRING | `org.login` | 개인 저장소는 null |
| `source_hour` | TINYINT | 파일명 | 어느 시간 파일에서 왔는지 |
| `ingested_at` | TIMESTAMP | 처리 시각 | |

**제외:** `public`(항상 true), `other`(display_login 만), 모든 `*_url`·`avatar_url`·`gravatar_id`·`node_id`

**규모:** 2022-01~2025-09 기준 약 50억 행. 행당 100바이트 미만이므로 압축 후 수백 GB 가 아니라 수십 GB 수준으로 예상된다.

**이것만으로 되는 것:** 부 목표 B 전체, 이벤트 타입 구성비 추이, 저장소·사용자 활동량, 품질 검증 지표

### `silver_refs` — 브랜치·태그 생성과 삭제

CreateEvent 와 DeleteEvent 를 하나로 합친다. 두 이벤트의 payload 구조가 거의 같고 짝지어 쓰기 때문이다.

| 컬럼 | 타입 | 출처 |
|---|---|---|
| `event_id` | STRING | `id` |
| `event_date` | DATE | 파티션 키 |
| `repo_id` | BIGINT | `repo.id` |
| `actor_id` | BIGINT | `actor.id` |
| `operation` | STRING | `create` / `delete` (이벤트 타입에서 파생) |
| `ref` | STRING | `payload.ref` |
| `ref_type` | STRING | `payload.ref_type` — `branch`/`tag`/`repository` |
| `master_branch` | STRING | `payload.master_branch` — CreateEvent 만 |
| `description` | STRING | `payload.description` — CreateEvent 만 |

**주의:** CreateEvent 의 `ref` 에는 `refs/heads/` 접두사가 없다. PushEvent 의 `ref` 와 형식이 다르므로 섞지 않는다.

**이것으로 되는 것:** 부 목표 A, 기본 브랜치 명칭 추이, 브랜치 수명

### `silver_pull_requests` — 스키마 진화 시연

2025-10 변경의 영향을 가장 크게 받은 테이블이다. **축 2의 증명이 여기서 이뤄진다.**

| 컬럼 | 타입 | 2025-09 이전 | 2025-10 이후 |
|---|---|---|---|
| `event_id` | STRING | `id` | 동일 |
| `event_date` | DATE | 파티션 키 | 동일 |
| `repo_id` | BIGINT | `repo.id` | 동일 |
| `actor_id` | BIGINT | `actor.id` | 동일 |
| `action` | STRING | `payload.action` | 동일 |
| `pr_number` | INT | `payload.number` | 동일 |
| `pr_id` | BIGINT | `pull_request.id` | 동일 |
| `head_ref` | STRING | `pull_request.head.ref` | 동일 |
| `base_ref` | STRING | `pull_request.base.ref` | 동일 |
| `labels` | ARRAY\<STRING\> | `pull_request.labels[].name` | **`labels[].name`** |
| `assignees` | ARRAY\<STRING\> | `pull_request.assignees[].login` | **`assignees[].login`** |
| `title` | STRING | `pull_request.title` | **null** |
| `body` | STRING | `pull_request.body` | **null** |
| `additions` | INT | `pull_request.additions` | **null** |
| `deletions` | INT | `pull_request.deletions` | **null** |
| `changed_files` | INT | `pull_request.changed_files` | **null** |
| `merged_at` | TIMESTAMP | `pull_request.merged_at` | **null** |
| `author_association` | STRING | `pull_request.author_association` | **null** |

**핵심 설계:** `labels` 와 `assignees` 는 **두 경로를 순차 탐색해 먼저 발견되는 쪽을 쓴다.** 한쪽만 읽으면 해당 시기가 통째로 빈다. 이 로직이 축 2 의 실질이다.

**커버리지 해석 주의:** 2025-09 이전에는 라벨이 없어도 빈 배열이 붙어 존재율 100%였고, 이후에는 실제로 있을 때만 키가 생긴다. 존재율 하락을 손실로 읽으면 안 된다.

---

## 파티션과 정렬

**파티션 키:** `event_date`. 하루 단위 재처리가 축 4 의 요구사항이므로 날짜가 자연스럽다.

**정렬 키:** `repo_id`. 부 목표 B 가 저장소별 시계열 집계라 저장소가 인접하면 스캔이 줄어든다.

**파일 크기:** 하루 파티션이 너무 작으면 small file 문제, 너무 크면 병렬도가 떨어진다. 축 5 에서 측정해 정한다.

**월 단위 파티션 대안:** 하루 단위는 4년치면 1,400개 이상의 파티션이 된다. 메타데이터 부담과 재처리 편의의 트레이드오프를 축 5 에서 비교한다.

---

## 품질 메타데이터

### `quality_daily`

`data_analysis/BQ_EDA/analysis/daily_volume.csv` 를 초기값으로 삼고, 파이프라인이 매 실행마다 갱신한다.

| 컬럼 | 내용 |
|---|---|
| `event_date` | DATE |
| `hours_present` | 존재한 시간별 파일 수 (0~24) |
| `event_count` | 이벤트 수 |
| `rolling_median` | 28일 이동 중앙값 |
| `count_ratio` | `event_count / rolling_median` |
| `hour_skew_ratio` | 최저 시간 / 최고 시간. 정상 0.55~0.58 |
| `quality_flag` | `ok` / `partial` / `degraded` |
| `checked_at` | TIMESTAMP |

`quality_flag` 기준값은 미확정. 초기 제안은 `count_ratio < 0.6` 또는 `hours_present < 24` 면 `partial`, `hour_skew_ratio > 0.9` 면 `degraded`.

### `ingest_log`

| 컬럼 | 내용 |
|---|---|
| `event_date`, `source_hour` | 처리 단위 |
| `status` | `pending` / `done` / `failed` |
| `row_count`, `bytes_in` | |
| `started_at`, `finished_at` | |
| `attempt` | 재시도 횟수 |

중단 지점부터 재개하는 근거이며 축 1 의 처리량 지표가 여기서 나온다.

---

## 스키마 드리프트 감지

2025-10 변경을 `if event_date >= '2025-10-07'` 로 처리하면 안 된다. 이미 답을 알고 짠 분기라
다음 변경에는 무력하고, 역량 증명도 되지 않는다. 변경을 처리하는 것이 아니라
**변경을 감지하는 장치**를 만든다.

### 원칙

**변환 코드에 날짜 리터럴을 넣지 않는다.** 이것이 하드코딩과 일반 규칙을 가르는 기준이며,
코드를 훑으면 바로 검증된다.

`coalesce(pull_request.labels, labels)` 는 변경이 언제 일어났든 동작한다.
`if date >= '2025-10-07'` 은 그 날짜에만 동작한다.

### 4단계

**1. 원본 보존** — bronze 에 원본 JSON 을 그대로 둔다. 예상하지 못한 필드가 들어와도 잃지 않는다.

**2. 방어적 파싱** — 필드가 없으면 null, 모르는 키는 버리지 않고 기록한다. 파서가 죽지 않는 것이 우선이다.

**3. 키 집합 감시** — 파티션마다 관측된 키 집합을 등록 스키마와 비교해 `schema_drift` 에 기록한다.

| 컬럼 | 내용 |
|---|---|
| `event_date` | DATE |
| `event_type` | STRING |
| `key_path` | 관측된 키 경로 |
| `change` | `new` / `missing` |
| `detected_at` | TIMESTAMP |

신규 이벤트 타입도 여기서 잡힌다.

**4. 분포 감시** — 키 집합 비교보다 중요하다. `pull_request.title` 은 컬럼이 남은 채 값만 null 이
됐으므로 키 비교로는 잡히지 않는다. 컬럼별 null 비율이 급변하는 것을 감시해야 잡힌다.

| 컬럼 | 내용 |
|---|---|
| `event_date`, `event_type`, `column_name` | 대상 |
| `null_ratio` | 해당 파티션의 null 비율 |
| `prev_null_ratio` | 직전 관측 파티션 |
| `delta` | 변화폭 |

임계값은 미확정. 초기 제안은 변화폭 0.5 이상.

### 구현 순서

정직성을 위해 순서를 지킨다. git 히스토리가 순서를 증명한다.

1. 감지기를 먼저 만든다 (대응 규칙 없이)
2. 전 기간을 순차 처리한다
3. `schema_drift` 와 null 비율 경보를 산출물로 남긴다
4. 로그를 근거로 대응 규칙(`coalesce` 등)을 추가한다

체인지로그를 미리 읽었다는 사실은 숨기지 않는다. 감지기가 독립적으로 같은 날짜를 짚어냈다면
그것이 감지기의 정확도를 검증한 것이 된다. BQ EDA 에서 `daily_volume.csv` 가
2025-10-09~14 를 먼저 잡아내고 이후 검색으로 GitHub Event API 장애임을 확인한 것과 같은 순서다.

---

## 장애 주입 테스트

**데이터 결손은 만들지 않는다.** 실제 사례가 이미 있다.

| 실제 사례 | 증명하는 축 |
|---|---|
| 2020-08-22 파일 부재 | 404 처리, 결측 기록 |
| 2020-08-21 09시 이후 시간 누락 | 부분 적재 탐지 |
| 2025-10-09~14 정상의 0.5% | 품질 게이팅 |
| 2025-10-07 payload 변경 | 스키마 드리프트 감지 |

실제 사례가 있는데 가짜 결측을 지어내면 오히려 약해진다.

**프로세스 장애는 데이터가 제공하지 못하므로 주입한다.**

| 주입 | 증명하는 축 |
|---|---|
| 배치 중간 프로세스 강제 종료 | 축 4 — 재개, 중복 없음, 반쪽 파티션 없음 |
| 손상된 `.gz` 투입 | 축 3 — 크래시 대신 격리 |
| 미지의 이벤트 타입 한 건 투입 | 축 2 — 버리지 않고 수용 |
| 같은 파티션 3회 재처리 | 축 4 — 행 수·체크섬 불변 |

**서술 규칙:** 주입한 실패를 사고인 것처럼 쓰지 않는다. "장애가 발생했다" 가 아니라
"이런 장애를 주입해 복구를 검증했다" 로 쓴다.

---

## 단계별 계획

### Phase 0 — 실측

원본 `.json.gz` 를 시기별로 받아 압축·해제 용량과 시간대별 편차를 잰다. 2020 / 2022 / 2024 / 2025 각 하루씩.

**이 결과로 정하는 것:** 처리 기간, 원본 보관 정책, 배치 크기

**막고 있는 것:** 이 숫자 없이는 아래 모든 단계의 규모를 잡을 수 없다.

### Phase 1 — bronze

다운로드와 원본 저장. 파싱은 최소화한다.

- 시간별 파일 다운로드, 재시도, 처리 이력 기록
- `ingest_log` 구현
- 3단계 품질 검증 중 1·2단계 (파일 존재, 이벤트 수)

### Phase 2 — silver_events

전 기간 평탄화. 파이프라인의 뼈대다.

- `event_id` 중복 제거
- 파티션 쓰기, 특정 날짜 재처리
- `quality_daily` 구현 (3단계 검증 완성)
- **축 4 증명:** 임의 날짜 3회 재처리 후 행 수·체크섬 불변 확인

### Phase 3 — silver_refs, silver_pull_requests

타입별 평탄화. 스키마 드리프트 감지가 여기서 동작한다.

- 감지기 먼저 구현 (`schema_drift`, null 비율 감시)
- 대응 규칙 없이 전 기간 처리 → 경보 로그 확보
- 로그를 근거로 `labels`·`assignees` 두 경로 통합 규칙 추가
- 2025-10 경계를 가로지르는 쿼리 검증

**축 2 증명:** 감지 로그와 그 이후의 대응 커밋. 경계 전후 동일 쿼리 동작

### Phase 3.5 — 장애 주입 테스트

위 "장애 주입 테스트" 절의 4가지를 수행하고 결과를 기록한다.

**축 3·4 증명**

### Phase 4 — 성능 튜닝

Phase 2·3 을 기준선으로 삼아 측정한다.

- 파티션 단위 비교
- 파일 크기 조정
- 압축 코덱 비교
- 병렬도·메모리 조정

**축 5 증명:** 전후 수치와 판단 근거

### Phase 5 — gold

부 목표 A·B 산출물.

- A: 브랜치 명명 분포 (문자열 파싱 워크로드)
- B: 저장소별 일별 스타와 4주 롤링 baseline (윈도 함수 워크로드)
- B 산출물에는 `quality_daily` 를 조인해 신뢰도를 표시한다

---

## 결정이 필요한 것

1. **저장 포맷** — Parquet + Hive 파티션이 단순하다. Iceberg 는 스키마 진화와 파티션 진화를 엔진이 처리해줘서 축 2·5 와 잘 맞지만 구성 복잡도가 올라간다
2. **처리 기간** — Phase 0 결과에 달렸다
3. **`quality_flag` 판정 기준값**
4. **파티션 단위** — Phase 4 에서 측정 후 확정. 초기값은 날짜
5. **원본 보관** — bronze 를 남길지, 처리 후 폐기할지. 용량에 달렸다