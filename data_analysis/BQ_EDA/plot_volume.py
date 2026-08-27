#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Plot the monthly volume trend produced by analyze_inventory.py.

Reads analysis/monthly_volume.csv and writes a two-panel PNG: events per day
on top, bytes per row below. Months with missing or partial data are shaded,
and months exceeding the break threshold are marked.

Labels are intentionally in English: matplotlib ships no Hangul font by
default, so Korean text renders as empty boxes on a stock install.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

MONTHLY_FILE = Path("analysis/monthly_volume.csv")
PLOT_FILE = Path("analysis/volume_trend.png")
BREAK_THRESHOLD = 0.25

GAP_COLOR = "#e8a0a0"
BREAK_COLOR = "#c0392b"
LINE_COLOR = "#2c3e50"


def load_monthly(monthly_file: Path) -> list[dict]:
    with monthly_file.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row["days"] = int(row["days"])
        row["missing_days"] = int(row["missing_days"])
        row["is_partial"] = int(row["is_partial"])
        row["rows_per_day"] = int(row["rows_per_day"])
        row["bytes_per_row"] = int(row["bytes_per_row"])
        for key in ("rows_change_pct", "bytes_change_pct"):
            row[key] = float(row[key]) if row[key] else None
    return rows


def thousands(value, _position) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


def shade_gaps(axis, rows: list[dict]) -> None:
    for index, row in enumerate(rows):
        if row["missing_days"] > 0 or row["is_partial"]:
            axis.axvspan(index - 0.5, index + 0.5, color=GAP_COLOR, alpha=0.35, zorder=0)


def draw_panel(
    axis,
    rows: list[dict],
    value_key: str,
    change_key: str,
    title: str,
    ylabel: str,
    threshold: float,
    log_scale: bool,
) -> None:
    values = [row[value_key] for row in rows]
    positions = range(len(rows))

    shade_gaps(axis, rows)
    axis.plot(positions, values, color=LINE_COLOR, linewidth=1.4, zorder=2)

    breaks = [
        (index, row[value_key])
        for index, row in enumerate(rows)
        if row[change_key] is not None and abs(row[change_key]) >= threshold * 100
    ]
    if breaks:
        axis.scatter(
            [b[0] for b in breaks],
            [b[1] for b in breaks],
            color=BREAK_COLOR,
            s=28,
            zorder=3,
            label=f"break (>= {threshold:.0%} MoM)",
        )

    if log_scale:
        axis.set_yscale("log")
    axis.set_title(title, fontsize=11, loc="left")
    axis.set_ylabel(ylabel, fontsize=9)
    axis.yaxis.set_major_formatter(FuncFormatter(thousands))
    axis.grid(True, alpha=0.25, linewidth=0.6)
    axis.margins(x=0.01)
    axis.legend(fontsize=8, loc="upper left")


def set_year_ticks(axis, rows: list[dict]) -> None:
    ticks = [index for index, row in enumerate(rows) if row["month"].endswith("01")]
    axis.set_xticks(ticks)
    axis.set_xticklabels([rows[i]["month"][:4] for i in ticks], rotation=45, fontsize=8)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly", type=Path, default=MONTHLY_FILE)
    parser.add_argument("--plot", type=Path, default=PLOT_FILE)
    parser.add_argument("--threshold", type=float, default=BREAK_THRESHOLD)
    args = parser.parse_args()

    if not args.monthly.is_file():
        print(f"monthly file not found: {args.monthly}")
        print("run analyze_inventory.py first")
        return 1

    rows = load_monthly(args.monthly)

    figure, (top, bottom) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    figure.suptitle(
        "githubarchive.day monthly volume  "
        "(shaded = month with missing or partial days)",
        fontsize=12,
    )

    draw_panel(
        top,
        rows,
        value_key="rows_per_day",
        change_key="rows_change_pct",
        title="Events per day (log scale)",
        ylabel="events / day",
        threshold=args.threshold,
        log_scale=True,
    )
    draw_panel(
        bottom,
        rows,
        value_key="bytes_per_row",
        change_key="bytes_change_pct",
        title="Bytes per row",
        ylabel="bytes / row",
        threshold=args.threshold,
        log_scale=False,
    )
    set_year_ticks(bottom, rows)

    figure.tight_layout()
    args.plot.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.plot, dpi=150)

    print(f"months : {len(rows)}")
    print(f"plot   : {args.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())