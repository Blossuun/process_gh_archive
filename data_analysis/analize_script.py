import json
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_FILE = SCRIPT_DIR / "2026-08-01-15.json.gz"
OUTPUT_FILE = SCRIPT_DIR / "data_preview.txt"

con = duckdb.connect()
con.execute(f"CREATE VIEW raw AS SELECT json FROM read_ndjson_objects('{DATA_FILE}')")

out = []

# 1. 레코드 한 건이 실제로 어떻게 생겼는지
sample = con.sql("SELECT json FROM raw LIMIT 1").fetchone()[0]
out.append("=== 샘플 레코드 1건 ===")
out.append(json.dumps(json.loads(sample), indent=2, ensure_ascii=False))

# 2. 공통 스키마 골격
structure = con.sql(
    "SELECT json_group_structure(json) FROM (SELECT json FROM raw LIMIT 500)"
).fetchone()[0]
out.append("\n=== 공통 스키마 골격 (500건 기준) ===")
out.append(json.dumps(json.loads(structure), indent=2, ensure_ascii=False))

# 3. 어떤 이벤트 타입이 얼마나 있는지
types = con.sql("""
    SELECT json_extract_string(json, '$.type') AS event_type, count(*) AS cnt
    FROM raw
    GROUP BY 1
    ORDER BY 2 DESC
""")
out.append("\n=== 이벤트 타입 분포 ===")
out.append(str(types))

OUTPUT_FILE.write_text("\n".join(out), encoding="utf-8")
con.close()
print(f"저장: {OUTPUT_FILE}")