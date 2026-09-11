-- ingest_log — (event_date, hour) 단위 처리 상태 기계
--
--   pending ──> downloaded ──> produced ──> processed
--      │            │             │            │
--      │            └─────────────┴────────────┴──> failed ──> pending
--      └──(404)──> missing

CREATE TABLE IF NOT EXISTS ingest_log (
    event_date      TEXT    NOT NULL,
    hour            INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    status          TEXT    NOT NULL DEFAULT 'pending',
    gz_bytes        INTEGER,
    raw_events      INTEGER,
    produced_events INTEGER,
    bronze_events   INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (event_date, hour)
);

CREATE INDEX IF NOT EXISTS ix_ingest_log_status ON ingest_log (status, event_date, hour);

-- 3단계 검증 중 2단계: 건수 불일치 = 소리 없는 데이터 손실.
-- <> 가 아니라 IS NOT 인 이유는 건수가 아예 기록되지 않은 NULL 도 잡아야 하기 때문.
CREATE VIEW IF NOT EXISTS count_mismatch AS
SELECT event_date, hour, raw_events, produced_events, bronze_events
  FROM ingest_log
 WHERE status = 'processed'
   AND (raw_events IS NOT produced_events OR produced_events IS NOT bronze_events);