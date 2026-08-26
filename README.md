# Process GH Archive
GH Archive 데이터를 제한된 하드웨어 리소스로 처리해보는 프로젝트.

## 목표

### Github 사용에 대한 관례 실태 조사

Github 사용법에 대한 방법론은 많지만, 다 조금씩 차이가 존재함.

Github에서 실제로 널리 통용되는 사용 관례는 무엇이며, 시간에 따라 어떻게 변해왔는가 조사.

### AI 모델이 아닌 트렌딩 OSS 리포 조사하기

Trending repository를 검색하면, AI 모델 repository가 많이 나오는데, 이는 내가 trending repository를 검색했을 때 알고 싶은 정보가 아니였다.

Trending repository 안에서도, OSS만을 선별해 주간 뜨는 repository 목록을 만들고, 유행하는 도구, 프레임워크를 조사할 예정이다.

이후에 월간 리포로 조사 범위를 확장할 계획.

스타 증가량과 더불어 포크 증가량도 함께 조사해 실사용량이 높은 리포를 알아볼 예정.

## 개발 환경

### 하드웨어

| 항목 | 사양 |
|---|---|
| CPU | AMD Ryzen 9 5900HS (8코어 16스레드) |
| RAM | 16GB |
| 저장소 | 954GB NVMe SSD |
| OS | Windows 10 Pro |

## 구조

### 1차 (실행 위주)

    GH Archive → Kafka → Spark → Parquet (시간 파티션) → DuckDB → exports/
                        ↑
                    Airflow

### 2차 (Iceberg 도입)

    GH Archive → Kafka → Spark → Iceberg 실버 → 골드 마트 → exports/
                        ↑
                    Airflow (적재 + 유지보수)

## EDA

### BigQuery Sandbox

- 카드 등록 없이 무료로 월 1TB의 쿼리가 무료
- GitHub Archive 공개 데이터셋을 조회 가능