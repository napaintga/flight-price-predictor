from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from add_flight_id_to_daily import (
    _build_flight_id_values,
    _ensure_departure_date,
    _ensure_search_date,
    _insert_after,
    _parse_file_date,
    iter_daily_csvs,
)


def _prepare_flight_keys(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    prepared = frame.copy()
    search_date = _parse_file_date(path)
    if (
        "search_date" not in prepared.columns
        or prepared["search_date"].astype("string").fillna("").str.strip().eq("").any()
    ):
        prepared = _ensure_search_date(prepared, search_date)

    if (
        "departure_date" not in prepared.columns
        or prepared["departure_date"].astype("string").fillna("").str.strip().eq("").any()
    ):
        prepared = _ensure_departure_date(prepared, search_date)

    if (
        "flight_id" not in prepared.columns
        or prepared["flight_id"].astype("string").fillna("").str.strip().eq("").any()
    ):
        generated_ids = pd.Series(
            _build_flight_id_values(prepared),
            index=prepared.index,
            dtype="string",
        )
        if "flight_id" in prepared.columns:
            current_ids = prepared["flight_id"].astype("string")
            missing_ids = current_ids.fillna("").str.strip().eq("")
            prepared["flight_id"] = current_ids
            prepared.loc[missing_ids, "flight_id"] = generated_ids.loc[missing_ids]
        else:
            prepared["flight_id"] = generated_ids

    column_order = list(prepared.columns)
    column_order = _insert_after(column_order, "search_date", "days_to_departure")
    column_order = _insert_after(column_order, "departure_date", "search_date")
    column_order = _insert_after(column_order, "flight_id", "departure_date")
    prepared = prepared[column_order]

    return prepared


def deduplicate_file(
    path: Path,
    *,
    mode: str = "flight_id",
    keep: str = "first",
    dry_run: bool = False,
) -> dict[str, object]:
    original = pd.read_csv(path)
    before = len(original)

    if mode == "flight_id":
        result = _prepare_flight_keys(original, path)
        deduped = result.drop_duplicates(subset=["flight_id"], keep=keep)
    else:
        deduped = original.drop_duplicates(keep=keep)

    after = len(deduped)
    removed = before - after

    if not dry_run:
        deduped.to_csv(path, index=False)

    return {
        "file": path.name,
        "rows_before": before,
        "rows_after": after,
        "duplicates_removed": removed,
        "mode": mode,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove duplicates from daily flight CSV files."
    )
    parser.add_argument(
        "--daily-dir",
        default="etl/exports/daily",
        help="Directory with daily CSV files.",
    )
    parser.add_argument(
        "--mode",
        choices=["flight_id", "row"],
        default="flight_id",
        help="Deduplicate by stable flight_id or by full row.",
    )
    parser.add_argument(
        "--keep",
        choices=["first", "last"],
        default="first",
        help="Which duplicate row to keep.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deduplication results without rewriting files.",
    )
    args = parser.parse_args()

    daily_dir = Path(args.daily_dir)
    if not daily_dir.exists():
        raise FileNotFoundError(f"Directory not found: {daily_dir}")

    files = iter_daily_csvs(daily_dir)
    if not files:
        print("No matching CSV files found.")
        return 0

    total_before = 0
    total_after = 0
    total_removed = 0

    for path in files:
        result = deduplicate_file(
            path,
            mode=args.mode,
            keep=args.keep,
            dry_run=args.dry_run,
        )
        total_before += int(result["rows_before"])
        total_after += int(result["rows_after"])
        total_removed += int(result["duplicates_removed"])

        action = "preview" if args.dry_run else "updated"
        print(
            f"{action}: {result['file']} "
            f"rows_before={result['rows_before']} "
            f"rows_after={result['rows_after']} "
            f"duplicates_removed={result['duplicates_removed']} "
            f"mode={result['mode']}"
        )

    print(
        "summary:",
        f"files={len(files)}",
        f"rows_before={total_before}",
        f"rows_after={total_after}",
        f"duplicates_removed={total_removed}",
        f"mode={args.mode}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
