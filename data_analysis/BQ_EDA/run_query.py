#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-cloud-bigquery>=3.25", "python-dotenv>=1.0"]
# ///
"""Execute a single .sql file against BigQuery and record its cost.

Always performs a dry run first. Aborts before execution if the estimated
scan exceeds MAX_BYTES_BILLED.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

MAX_BYTES_BILLED = 2_000_000_000  # 2 GB
JOB_LOCATION = "US"  # githubarchive resides in the US multi-region
PROJECT_ENV_VAR = "GOOGLE_CLOUD_PROJECT"
ENV_FILE = Path(__file__).resolve().parent / ".env"
LOG_FILE = Path("query_log.csv")
LOG_FIELDS = [
    "run_at",
    "query_file",
    "estimated_bytes",
    "billed_bytes",
    "row_count",
    "output_file",
    "status",
]


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:,.2f} {unit}"
        size /= 1024
    return f"{size:,.2f} TB"


SETUP_HINT = f"""
BigQuery project id could not be determined. Choose one of the following:

  1. write it into {ENV_FILE.name} next to this script
       {PROJECT_ENV_VAR}=YOUR_PROJECT_ID

  2. pass it explicitly
       uv run run_query.py <query.sql> --project YOUR_PROJECT_ID

  3. set it for the current shell session
       PowerShell : $env:{PROJECT_ENV_VAR} = "YOUR_PROJECT_ID"
       bash       : export {PROJECT_ENV_VAR}=YOUR_PROJECT_ID

  4. write it into the ADC credentials once
       gcloud auth application-default set-quota-project YOUR_PROJECT_ID
"""


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

    print(SETUP_HINT, file=sys.stderr)
    raise SystemExit(1)


def estimate(client: bigquery.Client, sql: str) -> int:
    config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(sql, job_config=config, location=JOB_LOCATION)
    return job.total_bytes_processed


def execute(client: bigquery.Client, sql: str, cap: int) -> bigquery.QueryJob:
    config = bigquery.QueryJobConfig(maximum_bytes_billed=cap)
    job = client.query(sql, job_config=config, location=JOB_LOCATION)
    job.result()  # block until finished
    return job


def write_output(rows: list[dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2, default=str)


def append_log(record: dict) -> None:
    is_new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(record)


def main() -> int:
    load_dotenv(ENV_FILE)  # existing environment variables take precedence

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query_file", type=Path, help="path to the .sql file")
    parser.add_argument("-o", "--output", type=Path, help="result JSON path")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_BYTES_BILLED,
        help=f"abort if the estimate exceeds this (default: {MAX_BYTES_BILLED})",
    )
    parser.add_argument(
        "--project",
        help=f"BigQuery project id (falls back to ${PROJECT_ENV_VAR}, .env, then ADC)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the estimate and exit without executing",
    )
    args = parser.parse_args()

    query_file: Path = args.query_file
    if not query_file.is_file():
        print(f"query file not found: {query_file}", file=sys.stderr)
        return 1

    sql = query_file.read_text(encoding="utf-8")
    output_file: Path = args.output or Path("results") / f"{query_file.stem}.json"
    project = resolve_project(args.project)
    client = bigquery.Client(project=project)

    estimated_bytes = estimate(client, sql)
    print(f"project : {project}")
    print(f"query   : {query_file}")
    print(f"estimate: {human_bytes(estimated_bytes)}")
    print(f"cap     : {human_bytes(args.max_bytes)}")

    if estimated_bytes > args.max_bytes:
        print("ABORTED: estimate exceeds the cap", file=sys.stderr)
        append_log(
            {
                "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "query_file": str(query_file),
                "estimated_bytes": estimated_bytes,
                "billed_bytes": 0,
                "row_count": 0,
                "output_file": "",
                "status": "aborted",
            }
        )
        return 2

    if args.dry_run:
        print("dry run only, nothing executed")
        return 0

    job = execute(client, sql, args.max_bytes)
    rows = [dict(row) for row in job.result()]
    write_output(rows, output_file)

    billed_bytes = job.total_bytes_billed or 0
    print(f"billed  : {human_bytes(billed_bytes)}")
    print(f"rows    : {len(rows):,}")
    print(f"output  : {output_file}")

    append_log(
        {
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query_file": str(query_file),
            "estimated_bytes": estimated_bytes,
            "billed_bytes": billed_bytes,
            "row_count": len(rows),
            "output_file": str(output_file),
            "status": "ok",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())