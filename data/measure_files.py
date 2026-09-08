# measure_files.py
import csv, gzip, re, sys, time
from pathlib import Path

RAW = Path("data/gharchive")
OUT = Path("data/meta/raw_file_stats.csv")
PAT = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{1,2})\.json\.gz$")
BIG = 1024 * 1024  # 1MB 이상 이벤트 = 이상치 후보

def key(p):
    m = PAT.search(p.name)
    return (m.group(1), int(m.group(2)))   # hour를 int로 → 정렬 문제 해결

files = sorted([p for p in RAW.rglob("*.json.gz") if PAT.search(p.name)], key=key)
OUT.parent.mkdir(parents=True, exist_ok=True)

with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["date", "hour", "filename", "gz_bytes", "raw_bytes", "events",
                "max_line_bytes", "big_lines", "empty_lines", "elapsed_sec"])
    for p in files:
        d, h = key(p)
        t0 = time.perf_counter()
        raw = events = mx = big = empty = 0
        with gzip.open(p, "rb") as f:
            for line in f:
                n = len(line)
                raw += n
                if n <= 1:          # 개행뿐인 줄
                    empty += 1
                    continue
                events += 1
                if n > mx:
                    mx = n
                if n >= BIG:
                    big += 1
        w.writerow([d, h, p.name, p.stat().st_size, raw, events,
                    mx, big, empty, round(time.perf_counter() - t0, 2)])
        fh.flush()
        print(f"{d}-{h:02d}  events={events:>7,}  max_line={mx/1024:>8,.0f}KB",
              file=sys.stderr)