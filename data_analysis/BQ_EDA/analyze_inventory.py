#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# ///
"""Summarise the githubarchive day-table inventory.

Reads the JSON produced by `run_query.py query/table_inventory.sql` and writes
a markdown report plus a monthly metrics CSV. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

INVENTORY_FILE = Path("results/table_inventory.json")
REPORT_FILE = Path("analysis/table_inventory_report.md")
MONTHLY_FILE = Path("analysis/monthly_volume.csv")
YEARLY_FILE = Path("analysis/yearly_volume.csv")

# A month whose bytes-per-row differs from the previous month by more than this
# fraction is flagged as a candidate structural break.
BREAK_THRESHOLD = 0.25

MONTHLY_FIELDS = [
    "month",
    "days",
    "expected_days",
    "missing_days",
    "is_partial",
    "rows",
    "size_bytes",
    "bytes_per_row",
    "prev_month",
    "prev_bytes_per_row",
    "bytes_change_pct",
    "rows_per_day",
    "prev_rows_per_day",
    "rows_change_pct",
    "prev_missing_days",
]

YEARLY_FIELDS = [
    "year",
    "days",
    "rows",
    "size_bytes",
    "rows_per_day",
    "prev_rows_per_day",
    "rows_change_pct",
    "gb_per_day",
    "prev_gb_per_day",
    "gb_change_pct",
    "bytes_per_row",
    "prev_bytes_per_row",
    "bytes_change_pct",
]


def to_date(table_id: str) -> date:
    return date(int(table_id[:4]), int(table_id[4:6]), int(table_id[6:8]))


def load_inventory(
    inventory_file: Path,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    records = json.loads(inventory_file.read_text(encoding="utf-8"))
    kept, skipped = [], []
    for record in records:
        table_id = record["table_id"]
        if len(table_id) == 8 and table_id.isdigit():
            kept.append(record)
        else:
            skipped.append(table_id)
    if skipped:
        print(f"skipped non-date table_ids: {skipped}")

    before = len(kept)
    if since:
        kept = [r for r in kept if r["table_id"] >= since]
    if until:
        kept = [r for r in kept if r["table_id"] <= until]
    if len(kept) != before:
        print(f"date filter kept {len(kept):,} of {before:,} tables")
    return kept


def find_missing_runs(records: list[dict]) -> list[list[date]]:
    present = {to_date(r["table_id"]) for r in records}
    first, last = min(present), max(present)

    runs: list[list[date]] = []
    cursor = first
    while cursor <= last:
        if cursor not in present:
            if runs and cursor - runs[-1][-1] == timedelta(days=1):
                runs[-1].append(cursor)
            else:
                runs.append([cursor])
        cursor += timedelta(days=1)
    return runs


def aggregate(records: list[dict], key_length: int) -> dict[str, dict]:
    buckets: dict[str, dict] = defaultdict(lambda: {"days": 0, "rows": 0, "size_bytes": 0})
    for record in records:
        key = record["table_id"][:key_length]
        buckets[key]["days"] += 1
        buckets[key]["rows"] += record["row_count"]
        buckets[key]["size_bytes"] += record["size_bytes"]
    return dict(buckets)


def bytes_per_row(bucket: dict) -> int:
    return round(bucket["size_bytes"] / bucket["rows"]) if bucket["rows"] else 0


def rows_per_day(bucket: dict) -> int:
    return round(bucket["rows"] / bucket["days"]) if bucket["days"] else 0


def gb_per_day(bucket: dict) -> float:
    if not bucket["days"]:
        return 0.0
    return round(bucket["size_bytes"] / bucket["days"] / 1024**3, 2)


def percent_change(current: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 1)


def month_bounds(month: str) -> tuple[date, date]:
    year, number = int(month[:4]), int(month[4:6])
    start = date(year, number, 1)
    next_month = date(year + (number == 12), number % 12 + 1, 1)
    return start, next_month - timedelta(days=1)


def build_monthly_rows(records: list[dict]) -> list[dict]:
    monthly = aggregate(records, key_length=6)
    observed = sorted(to_date(r["table_id"]) for r in records)
    first, last = observed[0], observed[-1]

    rows = []
    prev_month = None
    prev_bytes = None
    prev_rows = None
    prev_missing = None
    for month in sorted(monthly):
        bucket = monthly[month]
        start, end = month_bounds(month)
        # Days before the dataset begins or after it ends are not missing data.
        expected = (min(end, last) - max(start, first)).days + 1
        is_partial = start < first or end > last

        current_bytes = bytes_per_row(bucket)
        current_rows = rows_per_day(bucket)
        missing = expected - bucket["days"]
        rows.append(
            {
                "month": month,
                "days": bucket["days"],
                "expected_days": expected,
                "missing_days": missing,
                "is_partial": int(is_partial),
                "rows": bucket["rows"],
                "size_bytes": bucket["size_bytes"],
                "bytes_per_row": current_bytes,
                "prev_month": prev_month,
                "prev_bytes_per_row": prev_bytes,
                "bytes_change_pct": percent_change(current_bytes, prev_bytes),
                "rows_per_day": current_rows,
                "prev_rows_per_day": prev_rows,
                "rows_change_pct": percent_change(current_rows, prev_rows),
                "prev_missing_days": prev_missing,
            }
        )
        prev_month = month
        prev_bytes = current_bytes
        prev_rows = current_rows
        prev_missing = missing
    return rows


def build_yearly_rows(records: list[dict]) -> list[dict]:
    yearly = aggregate(records, key_length=4)
    rows = []
    prev_rows = None
    prev_gb = None
    prev_bytes = None
    for year in sorted(yearly):
        bucket = yearly[year]
        current_rows = rows_per_day(bucket)
        current_gb = gb_per_day(bucket)
        current_bytes = bytes_per_row(bucket)
        rows.append(
            {
                "year": year,
                "days": bucket["days"],
                "rows": bucket["rows"],
                "size_bytes": bucket["size_bytes"],
                "rows_per_day": current_rows,
                "prev_rows_per_day": prev_rows,
                "rows_change_pct": percent_change(current_rows, prev_rows),
                "gb_per_day": current_gb,
                "prev_gb_per_day": prev_gb,
                "gb_change_pct": percent_change(current_gb, prev_gb),
                "bytes_per_row": current_bytes,
                "prev_bytes_per_row": prev_bytes,
                "bytes_change_pct": percent_change(current_bytes, prev_bytes),
            }
        )
        prev_rows = current_rows
        prev_gb = current_gb
        prev_bytes = current_bytes
    return rows


def write_csv(rows: list[dict], fields: list[str], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def format_change(change_pct: float | None) -> str:
    return "-" if change_pct is None else f"{change_pct:+.1f}%"


def data_gap_note(row: dict) -> str:
    notes = []
    if row["is_partial"]:
        notes.append("부분 월")
    if row["missing_days"]:
        notes.append(f"결측 {row['missing_days']}일")
    if row["prev_missing_days"]:
        notes.append(f"직전 월 결측 {row['prev_missing_days']}일")
    return ", ".join(notes) if notes else "-"


def break_table(
    monthly_rows: list[dict],
    value_key: str,
    prev_key: str,
    change_key: str,
    value_label: str,
    threshold: float,
) -> list[str]:
    breaks = [
        row
        for row in monthly_rows
        if row[change_key] is not None and abs(row[change_key]) >= threshold * 100
    ]
    if not breaks:
        return ["임계값을 넘는 급변 없음."]

    lines = [
        f"| 직전 월 | 직전 {value_label} | 월 | {value_label} | 전월 대비 | 데이터 결손 |",
        "|---|---|---|---|---|---|",
    ]
    for row in breaks:
        lines.append(
            f"| {row['prev_month']} | {row[prev_key]:,} "
            f"| {row['month']} | {row[value_key]:,} "
            f"| {row[change_key]:+.1f}% | {data_gap_note(row)} |"
        )
    return lines


def creation_lag_days(record: dict) -> int:
    created = datetime.fromisoformat(record["created_at"]).date()
    return (created - to_date(record["table_id"])).days


def find_lagged(records: list[dict]) -> list[tuple[str, str, int]]:
    """Tables created later than their own date, i.e. delayed ingestion."""
    lagged = []
    for record in records:
        lag = creation_lag_days(record)
        if lag > 0:
            lagged.append((record["table_id"], record["created_at"][:10], lag))
    return lagged


def find_suspect_days(
    records: list[dict],
    missing_runs: list[list[date]],
    lagged: list[tuple[str, str, int]],
) -> list[tuple[str, str]]:
    """Days worth checking hour by hour, with the reason each was picked.

    An outage rarely stops at midnight UTC, so the days bordering a gap are the
    most likely to be present but only partly loaded.
    """
    present = {to_date(r["table_id"]) for r in records}
    reasons: dict[date, list[str]] = defaultdict(list)

    for run in missing_runs:
        for neighbour, side in ((run[0] - timedelta(days=1), "앞"), (run[-1] + timedelta(days=1), "뒤")):
            if neighbour in present:
                reasons[neighbour].append(f"결측 {run[0]}~{run[-1]} 의 {side}날")

    for table_id, _, lag in lagged:
        reasons[to_date(table_id)].append(f"생성 지연 {lag}일")

    return [
        (day.strftime("%Y%m%d"), " / ".join(notes))
        for day, notes in sorted(reasons.items())
    ]


def build_report(
    records: list[dict],
    missing_runs: list[list[date]],
    yearly_rows: list[dict],
    monthly_rows: list[dict],
    threshold: float,
    date_filter: str | None = None,
) -> str:
    dates = sorted(to_date(r["table_id"]) for r in records)
    first, last = dates[0], dates[-1]
    expected = (last - first).days + 1
    missing_days = sum(len(run) for run in missing_runs)
    empty_tables = [r["table_id"] for r in records if r["row_count"] == 0]

    lines: list[str] = []
    lines.append("# githubarchive.day 테이블 인벤토리 분석")
    lines.append("")
    lines.append(f"- 입력: `{INVENTORY_FILE.as_posix()}`")
    lines.append(f"- 급변 판정 임계값: 전월 대비 {threshold:.0%}")
    if date_filter:
        lines.append(f"- 적용 범위 필터: {date_filter}")
    lines.append("")

    lines.append("## 보유 범위")
    lines.append("")
    lines.append(f"- 기간: {first} ~ {last}")
    lines.append(f"- 보유 테이블: {len(records):,}개")
    lines.append(f"- 기간 내 총 일수: {expected:,}일")
    lines.append(f"- 결측: {missing_days}일")
    lines.append(f"- 행 수 0인 테이블: {len(empty_tables)}개")
    lines.append("")

    lines.append("## 결측 구간")
    lines.append("")
    if missing_runs:
        lines.append("| 시작 | 종료 | 일수 |")
        lines.append("|---|---|---|")
        for run in missing_runs:
            lines.append(f"| {run[0]} | {run[-1]} | {len(run)} |")
    else:
        lines.append("결측 없음.")
    lines.append("")

    lines.append("## 생성 지연")
    lines.append("")
    lines.append(
        "BigQuery 의 creation_time 은 이벤트 발생 시점이 아니라 테이블 객체가 "
        "만들어진 시점이다. 일일 자동 적재 구간에서 이 값이 테이블 날짜보다 "
        "늦다면 그날 적재가 지연됐다는 뜻이다. 결측으로도, 볼륨 급변으로도 "
        "잡히지 않는 이상을 드러낸다."
    )
    lines.append("")
    lagged = find_lagged(records)
    if lagged:
        lines.append("| 테이블 | 생성일 | 지연 |")
        lines.append("|---|---|---|")
        for table_id, created, lag in lagged:
            lines.append(f"| {table_id} | {created} | {lag}일 |")
    else:
        lines.append("생성 지연 없음.")
    lines.append("")

    lines.append("## 적재 이상 의심일")
    lines.append("")
    lines.append(
        "시간대별 적재 완전성을 확인할 후보. 적재 장애는 자정 UTC 에 맞춰 "
        "끝나지 않으므로, 결측 구간의 앞뒤 날은 테이블이 있으면서도 일부 "
        "시간대만 적재됐을 수 있다."
    )
    lines.append("")
    suspects = find_suspect_days(records, missing_runs, lagged)
    if suspects:
        lines.append("| 날짜 | 사유 |")
        lines.append("|---|---|")
        for table_id, reason in suspects:
            lines.append(f"| {table_id} | {reason} |")
    else:
        lines.append("의심일 없음.")
    lines.append("")

    lines.append("## 연도별 볼륨")
    lines.append("")
    lines.append(
        "첫 해와 마지막 해는 부분 연도다. 일수 열을 함께 확인할 것. "
        "전년 대비는 달력 길이 영향을 받지 않도록 일평균 값끼리 비교한다."
    )
    lines.append("")
    lines.append(
        "| 연도 | 일수 | 총 행 수 | 일평균 행 수 | 전년 대비 "
        "| 일평균 크기(GB) | 전년 대비 | 행당 바이트 | 전년 대비 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in yearly_rows:
        lines.append(
            f"| {row['year']} | {row['days']} | {row['rows']:,} "
            f"| {row['rows_per_day']:,} | {format_change(row['rows_change_pct'])} "
            f"| {row['gb_per_day']:.2f} | {format_change(row['gb_change_pct'])} "
            f"| {row['bytes_per_row']:,} | {format_change(row['bytes_change_pct'])} |"
        )
    lines.append("")

    lines.append("## 행당 바이트 급변 후보")
    lines.append("")
    lines.append(
        "행당 바이트는 payload 스키마 변화와 이벤트 타입 구성비 변화를 "
        "구분하지 못한다. 아래는 추가 확인이 필요한 후보 시점이다."
    )
    lines.append("")
    lines.extend(
        break_table(
            monthly_rows,
            value_key="bytes_per_row",
            prev_key="prev_bytes_per_row",
            change_key="bytes_change_pct",
            value_label="행당 바이트",
            threshold=threshold,
        )
    )
    lines.append("")

    lines.append("## 일평균 행 수 급변 후보")
    lines.append("")
    lines.append(
        "월별 일수 차이와 결측일을 상쇄하기 위해 총 행 수 대신 일평균 행 수를 쓴다. "
        "행당 바이트가 이벤트 한 건의 무게라면, 일평균 행 수는 이벤트 발생 건수다. "
        "두 지표가 함께 움직였는지 따로 움직였는지가 원인 구분의 단서가 된다."
    )
    lines.append("")
    lines.extend(
        break_table(
            monthly_rows,
            value_key="rows_per_day",
            prev_key="prev_rows_per_day",
            change_key="rows_change_pct",
            value_label="일평균 행 수",
            threshold=threshold,
        )
    )
    lines.append("")
    lines.append(f"월별 전체 수치는 `{MONTHLY_FILE.as_posix()}` 참조.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY_FILE)
    parser.add_argument("--report", type=Path, default=REPORT_FILE)
    parser.add_argument("--yearly", type=Path, default=YEARLY_FILE)
    parser.add_argument("--monthly", type=Path, default=MONTHLY_FILE)
    parser.add_argument("--threshold", type=float, default=BREAK_THRESHOLD)
    parser.add_argument(
        "--since",
        help="lower bound table_id, inclusive (YYYYMMDD)",
    )
    parser.add_argument(
        "--until",
        help="upper bound table_id, inclusive (YYYYMMDD)",
    )
    args = parser.parse_args()

    if not args.inventory.is_file():
        print(f"inventory file not found: {args.inventory}")
        return 1

    records = load_inventory(args.inventory, since=args.since, until=args.until)
    if not records:
        print("no tables left after filtering")
        return 1
    missing_runs = find_missing_runs(records)
    yearly_rows = build_yearly_rows(records)
    monthly_rows = build_monthly_rows(records)

    write_csv(yearly_rows, YEARLY_FIELDS, args.yearly)
    write_csv(monthly_rows, MONTHLY_FIELDS, args.monthly)

    date_filter = None
    if args.since or args.until:
        date_filter = f"since={args.since or '-'}, until={args.until or '-'}"

    report = build_report(
        records, missing_runs, yearly_rows, monthly_rows, args.threshold, date_filter
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    print(f"tables  : {len(records):,}")
    print(f"report  : {args.report}")
    print(f"yearly  : {args.yearly}")
    print(f"monthly : {args.monthly}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())