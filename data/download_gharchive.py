#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""Download GH Archive hourly files and record what happened.

GH Archive publishes one gzipped JSON Lines file per hour at
https://data.gharchive.org/{YYYY-MM-DD}-{H}.json.gz (hour is not zero padded).

Three failure modes this guards against:

  - A 404 or 500 body written to disk as if it were data. The status is
    checked before anything is written.
  - A half-finished download left behind by a dropped connection. Files are
    streamed to `.part` and renamed only after the gzip CRC verifies, so a
    partial file can never be mistaken for a complete one on the next run.
  - A hang with no timeout.

Some hours are genuinely absent from GH Archive - 2020-08-22 and 2021-05-08
among others. A 404 is recorded as `missing`, not as a failure, and does not
stop the run.

Every attempt is appended to a manifest CSV. It is the record of what was
downloaded, how large it was, and which hours are unavailable.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_URL = "https://data.gharchive.org"
OUTPUT_DIR = Path("gharchive")
MANIFEST_FILE = Path("download_manifest.csv")

CHUNK_SIZE = 1 << 20  # 1 MiB
TIMEOUT = (10, 120)  # connect, read
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 5

MANIFEST_FIELDS = [
    "date",
    "hour",
    "filename",
    "status",
    "bytes",
    "attempts",
    "elapsed_sec",
    "recorded_at",
]

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_MISSING = "missing"
STATUS_FAILED = "failed"


def hourly_range(start: datetime, end: datetime):
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def is_valid_gzip(path: Path) -> bool:
    """Read the whole file through gzip so a truncated body is caught."""
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(CHUNK_SIZE):
                pass
    except (OSError, EOFError, gzip.BadGzipFile):
        return False
    return True


def download(url: str, target: Path) -> tuple[str, int, int]:
    """Return (status, bytes, attempts). Never leaves a partial file behind."""
    partial = target.with_suffix(target.suffix + ".part")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as response:
                if response.status_code == 404:
                    return STATUS_MISSING, 0, attempt
                response.raise_for_status()

                with partial.open("wb") as handle:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        handle.write(chunk)

            if not is_valid_gzip(partial):
                raise OSError("gzip verification failed")

            size = partial.stat().st_size
            partial.replace(target)  # atomic on the same filesystem
            return STATUS_OK, size, attempt

        except (requests.RequestException, OSError) as error:
            partial.unlink(missing_ok=True)
            if attempt == MAX_ATTEMPTS:
                print(f"  failed after {attempt} attempts: {error}", file=sys.stderr)
                return STATUS_FAILED, 0, attempt
            time.sleep(BACKOFF_SECONDS * attempt)

    return STATUS_FAILED, 0, MAX_ATTEMPTS


def append_manifest(manifest_file: Path, record: dict) -> None:
    is_new = not manifest_file.exists()
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with manifest_file.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD-H, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD-H, inclusive")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="verify existing files instead of skipping them",
    )
    args = parser.parse_args()

    try:
        start = datetime.strptime(args.start, "%Y-%m-%d-%H")
        end = datetime.strptime(args.end, "%Y-%m-%d-%H")
    except ValueError:
        print("dates must look like 2025-09-24-0", file=sys.stderr)
        return 1
    if start > end:
        print("--start is after --end", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    totals = {STATUS_OK: 0, STATUS_SKIPPED: 0, STATUS_MISSING: 0, STATUS_FAILED: 0}
    downloaded_bytes = 0

    for moment in hourly_range(start, end):
        filename = f"{moment:%Y-%m-%d}-{moment.hour}.json.gz"
        target = args.output / filename
        began = time.monotonic()

        if target.exists() and not args.recheck:
            status, size, attempts = STATUS_SKIPPED, target.stat().st_size, 0
        elif target.exists() and args.recheck:
            if is_valid_gzip(target):
                status, size, attempts = STATUS_SKIPPED, target.stat().st_size, 0
            else:
                print(f"{filename}: corrupt, re-downloading")
                target.unlink()
                status, size, attempts = download(f"{BASE_URL}/{filename}", target)
        else:
            status, size, attempts = download(f"{BASE_URL}/{filename}", target)

        elapsed = round(time.monotonic() - began, 2)
        totals[status] += 1
        if status == STATUS_OK:
            downloaded_bytes += size

        append_manifest(
            args.manifest,
            {
                "date": f"{moment:%Y-%m-%d}",
                "hour": moment.hour,
                "filename": filename,
                "status": status,
                "bytes": size,
                "attempts": attempts,
                "elapsed_sec": elapsed,
                "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
        )

        if status in (STATUS_OK, STATUS_MISSING, STATUS_FAILED):
            print(f"{filename}: {status} ({size / 1024 / 1024:.1f} MB, {elapsed}s)")

    print()
    print(f"ok       : {totals[STATUS_OK]}")
    print(f"skipped  : {totals[STATUS_SKIPPED]}")
    print(f"missing  : {totals[STATUS_MISSING]}")
    print(f"failed   : {totals[STATUS_FAILED]}")
    print(f"downloaded: {downloaded_bytes / 1024 / 1024 / 1024:.2f} GB")
    print(f"manifest : {args.manifest}")

    return 1 if totals[STATUS_FAILED] else 0


if __name__ == "__main__":
    raise SystemExit(main())