# Process GH Archive

GH Archive 데이터를 제한된 하드웨어 리소스로 처리해보는 프로젝트.

## 목표

### 주 목표 — silver 테이블 파이프라인

중첩 JSON 이벤트 로그를 질의 가능한 정형 테이블로 변환하는 배치 파이프라인.
**이 프로젝트의 산출물은 파이프라인이다.** 분석 결과는 파이프라인이 쓸 만한 데이터를
만들어낸다는 증명이며, 그 자체가 목적은 아니다.

| 축 | 내용 |
|---|---|
| 규모 | 수년치를 실제로 처리하고 처리량·소요 시간을 기록 |
| 스키마 진화 | 변경을 감지하는 장치를 만들고, 감지 후 대응 규칙을 추가 |
| 품질 게이팅 | 부실한 데이터를 자동 탐지·격리. 값을 보간하지 않음 |
| 멱등성·재처리 | 같은 날짜를 여러 번 처리해도 결과 동일 |
| 성능 튜닝 | 파티션·파일 크기·압축 선택에 수치 근거를 남김 |

상세는 [`goals.md`](goals.md), 스키마와 단계별 계획은 [`silver_design.md`](silver_design.md).

### 부 목표 — 파이프라인 산출물의 활용

분석 항목은 인사이트가 아니라 **기술 부하의 성격**으로 골랐다.

- **브랜치 명명 분포** — 수억 건 문자열 파싱과 대규모 집계
- **저장소별 일별 스타와 4주 롤링 baseline** — 대규모 윈도 함수와 시계열 조인

## 데이터 상태

BigQuery 공개 데이터셋으로 사전 조사한 결과, 이 데이터에는 실제 사건이 기록되어 있다.

- **2025-10-07** — GitHub Events API 정책 변경으로 payload 필드 대폭 제거.
  `pull_request` 48개 필드 중 43개 소멸, `PushEvent` 의 `commits` 배열 삭제
- **2025-10-08 ~ 14** — GitHub Event API 장애로 이벤트 약 20% 영구 결손
- **2025년 중반 이후** — `PushEvent` 외 이벤트가 심하게 과소 집계
- **결측 8일, 부분 적재 59일** (2016-07 이후 기준)

분석 결론을 내기에는 제약이지만, 데이터 엔지니어링 재료로는 좋다.
실제 breaking change, 실제 품질 결손, 실제 규모가 모두 갖춰져 있다.

조사 과정과 근거는 [`data_analysis/BQ_EDA/`](data_analysis/BQ_EDA/).

## 개발 환경

| 항목 | 사양 |
|---|---|
| CPU | AMD Ryzen 9 5900HS (8코어 16스레드) |
| RAM | 16GB |
| 저장소 | 954GB NVMe SSD |
| OS | Windows 10 Pro |

## 구조

### 1차 — Parquet

    GH Archive → Kafka → Spark → bronze → silver (Parquet, 날짜 파티션) → gold → exports/
                          ↑
                       Airflow

파티션 디렉터리를 Hive 스타일(`event_date=2025-09-24/`)로 유지한다.
Iceberg 가 `add_files` 로 기존 파일을 그대로 흡수할 수 있어야 하기 때문.

### 2차 — Iceberg 도입

    GH Archive → Kafka → Spark → bronze → silver (Iceberg) → gold → exports/
                          ↑
                       Airflow (적재 + 유지보수)

## 진행 상황

- [x] BigQuery 사전 조사 — 필드 카탈로그, 데이터 품질 파악
- [ ] Phase 0 — 원본 `.json.gz` 용량 실측
- [ ] Phase 1 — bronze
- [ ] Phase 2 — silver_events
- [ ] Phase 3 — silver_refs, silver_pull_requests
- [ ] Phase 4 — 성능 튜닝
- [ ] Phase 5 — gold

## 문서

| 문서 | 내용 |
|---|---|
| [`goals.md`](goals.md) | 목표 5개 축, 부 목표, 범위 밖 항목과 이유 |
| [`silver_design.md`](silver_design.md) | 테이블 스키마, 드리프트 감지, 단계별 계획 |
| [`data_analysis/BQ_EDA/analysis/findings.md`](data_analysis/BQ_EDA/analysis/findings.md) | 데이터 상태와 근거 |
| [`data_analysis/BQ_EDA/analysis/field_reference.md`](data_analysis/BQ_EDA/analysis/field_reference.md) | 필드별 내용과 함정 |