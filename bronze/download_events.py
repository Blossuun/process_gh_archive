#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""ingest_log 의 pending/failed 시간대를 내려받고 상태를 전이시킨다.

    uv run download_events.py                    대기 중인 전부
    uv run download_events.py --limit 24         24건만

GH Archive 는 시간당 gzip JSON Lines 파일 하나를 낸다. 시간은 zero-padding 이 없다.
    https://data.gharchive.org/{YYYY-MM-DD}-{H}.json.gz

막고 있는 실패 방식 세 가지.
  - 404 나 500 본문이 데이터인 양 디스크에 남는 것. 상태 코드를 먼저 본다.
  - 끊긴 연결이 남긴 반쪽 파일. .part 로 받고 gzip CRC 가 통과한 뒤에만 rename 한다.
  - 타임아웃 없는 무한 대기.

GH Archive 에는 원래 없는 시간대가 있다(2020-08-22, 2021-05-08 등).
404 는 실패가 아니라 missing 으로 기록하고 계속 진행한다.

gzip 검증은 어차피 파일 전체를 읽으므로 그 김에 줄 수를 센다.
이 값이 raw_events 이고, 검증 2단계의 기준이 된다.
"""

from __future__ import annotations

import argparse
import gzip
import sys
import time

import requests

import ingest_log
from ingest_log import REPO_ROOT

BASE_URL = "https://data.gharchive.org"
OUTPUT_DIR = REPO_ROOT / "data" / "gharchive"

CHUNK_SIZE = 1 << 20  # 1 MiB
TIMEOUT = (10, 120)   # connect, read
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 5


def verify_and_count(path) -> int | None:
    """gzip 을 끝까지 읽어 줄 수를 센다. 잘린 파일이면 None.

    검증과 카운트를 한 번의 읽기로 끝낸다. 나중에 다시 풀면 파일당 15초가 더 든다.
    """
    lines, last = 0, b"\n"
    try:
        with gzip.open(path, "rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                lines += chunk.count(b"\n")
                last = chunk[-1:]
    except (OSError, EOFError, gzip.BadGzipFile):
        return None
    return lines + (0 if last == b"\n" else 1)  # 마지막 줄에 개행이 없을 수 있다


def download(url: str, target) -> tuple[str, int, int, str]:
    """(status, bytes, raw_events, error) 를 돌려준다. 반쪽 파일을 남기지 않는다."""
    partial = target.with_suffix(target.suffix + ".part")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as response:
                if response.status_code == 404:
                    return "missing", 0, 0, ""
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        handle.write(chunk)

            events = verify_and_count(partial)
            if events is None:
                raise OSError("gzip 검증 실패")

            size = partial.stat().st_size
            partial.replace(target)  # 같은 파일시스템 안에서는 원자적
            return "downloaded", size, events, ""

        except (requests.RequestException, OSError) as error:
            partial.unlink(missing_ok=True)
            if attempt == MAX_ATTEMPTS:
                return "failed", 0, 0, f"{type(error).__name__}: {error}"
            time.sleep(BACKOFF_SECONDS * attempt)

    return "failed", 0, 0, "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="처리할 건수. 0 은 전부")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    totals: dict[str, int] = {}
    total_bytes = 0

    with ingest_log.connect() as conn:
        targets = conn.execute(
            "SELECT event_date, hour FROM ingest_log WHERE status IN ('pending', 'failed')"
            " ORDER BY event_date, hour" + (" LIMIT ?" if args.limit else ""),
            (args.limit,) if args.limit else (),
        ).fetchall()

        if not targets:
            print("대기 중인 시간대가 없다")
            return 0

        for row in targets:
            date, hour = row["event_date"], row["hour"]
            filename = f"{date}-{hour}.json.gz"  # 시간은 zero-padding 없음
            target = OUTPUT_DIR / filename
            began = time.monotonic()

            # 이미 있는 파일도 한 번은 읽어야 한다. raw_events 가 아직 비어 있고,
            # 이전 실행이 파일을 받아둔 채 기록 전에 죽었을 수 있다.
            error = ""
            if target.exists():
                events = verify_and_count(target)
                if events is None:
                    print(f"{filename}: 손상, 다시 받는다")
                    target.unlink()
                    status, size, events, error = download(f"{BASE_URL}/{filename}", target)
                else:
                    status = "downloaded"
            else:
                status, size, events, error = download(f"{BASE_URL}/{filename}", target)

            if status == "downloaded":
                size = target.stat().st_size
                ingest_log.transition(conn, date, hour, "downloaded",
                                      gz_bytes=size, raw_events=events)
                total_bytes += size
            elif status == "missing":
                ingest_log.transition(conn, date, hour, "missing", gz_bytes=0, raw_events=0)
                size = 0
            else:
                ingest_log.transition(conn, date, hour, "failed",
                                      last_error=error or "gzip 검증 실패")
                size = 0
                print(f"{filename}: 실패 — {error}", file=sys.stderr)

            totals[status] = totals.get(status, 0) + 1
            print(f"{filename}: {status} ({size / 2**20:.1f} MB, {events:,}건,"
                  f" {time.monotonic() - began:.1f}s)")

    print()
    for status, n in sorted(totals.items()):
        print(f"{status:<12}{n:>5}")
    print(f"{'내려받음':<10}{total_bytes / 2**30:>8.2f} GB")
    return 1 if totals.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())