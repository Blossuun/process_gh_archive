# measure_raw.py
import gzip, sys, json
from pathlib import Path
from collections import defaultdict

stats = defaultdict(lambda: {"files":0, "gz":0, "raw":0, "events":0})
for p in sorted(Path("data/gharchive").rglob("*.json.gz")):
    d = p.name[:10]
    s = stats[d]
    s["files"] += 1
    s["gz"] += p.stat().st_size
    with gzip.open(p, "rb") as f:
        for line in f:
            s["raw"] += len(line)
            s["events"] += 1
    print(f"{p.name} done", file=sys.stderr)

for d, s in sorted(stats.items()):
    print(json.dumps({
        "date": d, "files": s["files"],
        "gz_mb": round(s["gz"]/1024**2, 1),
        "raw_mb": round(s["raw"]/1024**2, 1),
        "ratio": round(s["raw"]/s["gz"], 2),
        "events": s["events"],
    }, ensure_ascii=False))