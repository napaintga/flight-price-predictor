from __future__ import annotations

import argparse
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

FILE_DATE_RE = re.compile(
    r"^(?P<prefix>flight|flights)_(?P<date>\d{4}-\d{2}-\d{2}|\d{2}_\d{2}(?:_\d{2})?)\.csv$",
    re.IGNORECASE,
)


def _parse_file_date(path: Path) -> date:
    match = FILE_DATE_RE.match(path.name)
    modified_local = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    if not match:
        return modified_local.date()

    raw_date = match.group("date")
    if "-" in raw_date:
        return date.fromisoformat(raw_date)

    parts = raw_date.split("_")
    if len(parts) == 3:
        day_part, month_part, year_part = parts
        return date(2000 + int(year_part), int(month_part), int(day_part))

    if len(parts) == 2:
        day_part, month_part = parts
        return date(modified_local.year, int(month_part), int(day_part))

    return modified_local.date()


def _build_departure_dates(
    days_to_departure: pd.Series, search_date: date
) -> pd.Series:
    days_numeric = pd.to_numeric(days_to_departure, errors="coerce")
    departure_dates = days_numeric.apply(
        lambda value: (
            search_date + timedelta(days=int(value))
            if pd.notna(value)
            else pd.NA
        )
    )
    return departure_dates.astype("string")


def _insert_after(
    columns: list[str], new_column: str, after_column: str
) -> list[str]:
    if new_column in columns:
        columns = [column for column in columns if column != new_column]
    if after_column not in columns:
        return [new_column, *columns]
    index = columns.index(after_column) + 1
    return columns[:index] + [new_column] + columns[index:]


def add_departure_date_column(path: Path, dry_run: bool = False) -> dict[str, object]:
    frame = pd.read_csv(path)
    if "days_to_departure" not in frame.columns:
        raise ValueError(f"{path.name}: missing 'days_to_departure' column")

    search_date = _parse_file_date(path)
    frame["search_date"] = search_date.isoformat()
    frame["departure_date"] = _build_departure_dates(
        frame["days_to_departure"], search_date
    )
    columns = _insert_after(list(frame.columns), "search_date", "days_to_departure")
    columns = _insert_after(columns, "departure_date", "search_date")
    frame = frame[columns]

    if not dry_run:
        frame.to_csv(path, index=False)

    return {
        "file": path.name,
        "rows": len(frame),
        "search_date": search_date.isoformat(),
        "dry_run": dry_run,
    }


def iter_daily_csvs(daily_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in daily_dir.glob("*.csv")
        if path.is_file() and FILE_DATE_RE.match(path.name)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add departure_date column to all daily ETL CSV files."
    )
    parser.add_argument(
        "--daily-dir",
        default="etl/exports/daily",
        help="Directory with daily CSV files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without rewriting files.",
    )
    args = parser.parse_args()

    daily_dir = Path(args.daily_dir)
    if not daily_dir.exists():
        raise FileNotFoundError(f"Directory not found: {daily_dir}")

    files = iter_daily_csvs(daily_dir)
    if not files:
        print("No matching CSV files found.")
        return 0

    for path in files:
        result = add_departure_date_column(path, dry_run=args.dry_run)
        mode = "preview" if args.dry_run else "updated"
        print(
            f"{mode}: {result['file']} rows={result['rows']} "
            f"search_date={result['search_date']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
