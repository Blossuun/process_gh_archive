"""ingest_log — 처리 상태 기계. 테이블 정의는 schema.sql 에 있다."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# 실행 위치와 무관하게 프로젝트 루트의 data/ 를 가리킨다.
# bronze/ 안에서 돌리든 루트에서 돌리든 같은 DB 를 본다.
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "ingest_log.db"
SCHEMA_PATH = Path(__file__).parent / "query" / "bronze_schema.sql"

# 각 상태로 들어올 수 있는 직전 상태. 자기 자신을 포함시켜 같은 전이의 재호출을 허용한다.
ALLOWED_FROM = {
    "downloaded": ("pending", "failed", "downloaded"),
    "missing":    ("pending", "failed", "missing"),
    "produced":   ("downloaded", "failed", "produced"),
    "processed":  ("produced", "failed", "processed"),
    "failed":     ("pending", "downloaded", "produced", "processed"),
    "pending":    ("failed", "pending"),
}


@contextmanager
def connect(db_path: Path = DB_PATH):
    """WAL + busy_timeout. 워커 여러 개가 동시에 쓰는 것을 전제한다."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        yield conn
    finally:
        conn.close()


def transition(conn, event_date: str, hour: int, to: str, **cols) -> None:
    """상태 전이. 허용되지 않으면 ValueError.

    전이 판정을 WHERE 절에 넣어 조회 없이 한 번의 UPDATE 로 끝낸다.
    cols 로 gz_bytes / raw_events / produced_events / bronze_events / last_error 갱신.
    """
    froms = ALLOWED_FROM[to]
    sets = ["status = ?", "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"]
    sets += [f"{k} = ?" for k in cols]
    if to == "failed":
        sets.append("attempts = attempts + 1")

    cur = conn.execute(
        f"UPDATE ingest_log SET {', '.join(sets)} WHERE event_date = ? AND hour = ?"
        f" AND status IN ({','.join('?' * len(froms))})",
        [to, *cols.values(), event_date, hour, *froms],
    )
    if cur.rowcount == 0:
        row = conn.execute(
            "SELECT status FROM ingest_log WHERE event_date=? AND hour=?", (event_date, hour)
        ).fetchone()
        raise ValueError(f"{event_date} {hour:02d}시: {row['status'] if row else '미등록'} -> {to} 불가")