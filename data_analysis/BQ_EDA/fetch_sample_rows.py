#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-cloud-bigquery>=3.25", "python-dotenv>=1.0"]
# ///
"""Fetch whole raw rows from a BigQuery table without incurring query cost.

Uses tabledata.list, the API behind the console's Preview tab. It creates no
query job, so no bytes are scanned or billed no matter how heavy the columns
are. That makes it the only affordable way to read complete `payload` values,
which cost 12.6 GB per day to scan with SQL.

Rows arrive in storage order rather than at random, so this is a structural
sample, not a statistical one. It answers "what does a row of this type look
like", not "how often does this happen".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

PROJECT_ENV_VAR = "GOOGLE_CLOUD_PROJECT"
ENV_FILE = Path(__file__).resolve().parent / ".env"

SCAN_LIMIT = 20_000  # rows read from the table before giving up
PER_TYPE = 3  # rows kept per event type


def resolve_project(cli_project: str | None) -> str:
    if cli_project:
        return cli_project

    env_project = os.environ.get(PROJECT_ENV_VAR)
    if env_project:
        return env_project

    try:
        _, adc_project = google.auth.default()
    except DefaultCredentialsError:
        print(
            "no application default credentials found. run:\n"
            "  gcloud auth application-default login",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if adc_project:
        return adc_project

    print(
        f"project id not found. set it in {ENV_FILE.name} or pass --project",
        file=sys.stderr,
    )
    raise SystemExit(1)


def to_plain(value):
    """Convert BigQuery row values into something json.dumps can handle."""
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def collect(
    client: bigquery.Client,
    table_id: str,
    scan_limit: int,
    per_type: int,
) -> tuple[dict[str, list[dict]], int]:
    table = client.get_table(table_id)
    buckets: dict[str, list[dict]] = defaultdict(list)

    scanned = 0
    for row in client.list_rows(table, max_results=scan_limit):
        scanned += 1
        record = {key: to_plain(value) for key, value in dict(row).items()}
        event_type = record.get("type")
        if len(buckets[event_type]) < per_type:
            buckets[event_type].append(record)
    return dict(buckets), scanned


def main() -> int:
    load_dotenv(ENV_FILE)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tables",
        nargs="+",
        help="fully qualified tables, e.g. githubarchive.day.20250924",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="directory for the per-table JSON files (default: results)",
    )
    parser.add_argument("--project", help=f"BigQuery project id (or ${PROJECT_ENV_VAR})")
    parser.add_argument("--scan-limit", type=int, default=SCAN_LIMIT)
    parser.add_argument("--per-type", type=int, default=PER_TYPE)
    args = parser.parse_args()

    project = resolve_project(args.project)
    client = bigquery.Client(project=project)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"project : {project}")

    for table_id in args.tables:
        output_file = args.output_dir / f"rows_{table_id.split('.')[-1]}.json"
        buckets, scanned = collect(client, table_id, args.scan_limit, args.per_type)
        with output_file.open("w", encoding="utf-8") as handle:
            json.dump(buckets, handle, ensure_ascii=False, indent=2, default=str)
        counts = ", ".join(
            f"{name}={len(rows)}" for name, rows in sorted(buckets.items())
        )
        print(f"{table_id}: scanned {scanned:,}, types {len(buckets)} -> {output_file}")
        print(f"  {counts}")

    print("billed  : 0 B (tabledata.list creates no query job)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())