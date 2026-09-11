#!/usr/bin/env python
"""처리 대상 (date, hour) 를 ingest_log 에 pending 으로 등록한다. 재실행해도 결과는 같다.

    uv run seed_ingest_log.py 2025-09-01 2025-09-30
    uv run seed_ingest_log.py 2020-08-12
"""

import sys
from datetime import date, timedelta

import ingest_log

args = sys.argv[1:]
if not 1 <= len(args) <= 2:
    sys.exit(__doc__)

start = date.fromisoformat(args[0])
end = date.fromisoformat(args[-1])
if start > end:
    sys.exit("시작일이 종료일보다 늦다")

days = [start + timedelta(n) for n in range((end - start).days + 1)]

with ingest_log.connect() as conn:
    cur = conn.executemany(
        "INSERT OR IGNORE INTO ingest_log (event_date, hour) VALUES (?, ?)",
        [(d.isoformat(), h) for d in days for h in range(24)],
    )
    print(f"대상 {len(days)}일 x 24시간 = {len(days) * 24}건")
    for row in conn.execute("SELECT status, COUNT(*) n FROM ingest_log GROUP BY status"):
        print(f"  {row['status']:<11}{row['n']:>6}")