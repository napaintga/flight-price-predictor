import argparse
from pathlib import Path

import pandas as pd
from add_flight_id_to_daily import (
    _build_flight_id_values,
    _ensure_departure_date,
    _ensure_search_date,
    _parse_file_date,
    iter_daily_csvs,
)

FEATURE_COLUMNS = [
    "days_to_departure",
    "search_date",
    "departure_date",
    "flight_id",
    "origin",
    "destination",
    "distance_km",
    "origin_type",
    "destination_type",
    "airline",
    "travel_class",
    "passengers_total",
    "trip_type",
    "stops",
    "duration_minutes",
    "price",
    "depart_hour",
    "departure_time",
    "arrival_time",
    "depart_dow",
    "depart_month",
    "depart_is_weekend",
    "depart_season",
    "is_holiday_depart",
    "search_dow",
    "search_month",
    "search_is_weekend",
    "search_season",
]

STRING_COLUMNS = [
    "search_date",
    "departure_date",
    "flight_id",
    "origin",
    "destination",
    "origin_type",
    "destination_type",
    "airline",
    "travel_class",
    "trip_type",
    "departure_time",
    "arrival_time",
]

OPTIONAL_COLUMNS = {
    "search_date",
    "departure_date",
    "flight_id",
}

DEDUPLICATE_COLUMNS = [
    "search_date",
    "flight_id",
]


def _load_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    return pd.read_csv(path, low_memory=False)


def _align_columns(frame):
    aligned = frame.copy()
    for col in FEATURE_COLUMNS:
        if col not in aligned.columns:
            aligned[col] = pd.NA
    return aligned[FEATURE_COLUMNS]


def _normalize_string_columns(frame):
    normalized = frame.copy()
    for col in STRING_COLUMNS:
        if col not in normalized.columns:
            continue
        normalized[col] = normalized[col].astype("string").str.strip()
        normalized[col] = normalized[col].replace(
            {"": pd.NA, "nan": pd.NA, "None": pd.NA, "null": pd.NA}
        )
    if "travel_class" in normalized.columns:
        normalized["travel_class"] = normalized["travel_class"].map(_normalize_travel_class)
    return normalized


def _normalize_travel_class(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    normalized = text.lower()
    if normalized in {"economy", "economy class"}:
        return "Economy Class"
    if normalized in {"premium economy", "premium economy class"}:
        return "Premium Economy"
    if normalized in {"business", "business class"}:
        return "Business Class"
    if normalized in {"first", "first class"}:
        return "First Class"
    return text or pd.NA


def _prepare_daily_frame(file_path, frame):
    prepared = frame.copy()
    search_date = _parse_file_date(file_path)

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

    return prepared


def _prepare_historical_frame(frame):
    prepared = frame.copy()
    if "search_date" not in prepared.columns:
        prepared["search_date"] = pd.NA

    if (
        "departure_date" in prepared.columns
        and (
            "flight_id" not in prepared.columns
            or prepared["flight_id"].astype("string").fillna("").str.strip().eq("").any()
        )
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

    return prepared


def _empty_summary(frame):
    empty_counts = frame.isna().sum()
    non_zero = {col: int(count) for col, count in empty_counts.items() if int(count) > 0}
    rows_with_empty_any = int(frame.isna().any(axis=1).sum())
    required_columns = [col for col in FEATURE_COLUMNS if col not in OPTIONAL_COLUMNS]
    rows_with_empty_required = int(frame[required_columns].isna().any(axis=1).sum())
    return rows_with_empty_any, rows_with_empty_required, non_zero


def merge_and_clean(daily_dir, old_features_path, output_path):
    frames = []

    daily_files = iter_daily_csvs(daily_dir) if daily_dir.exists() else []
    print(f"merge: daily_files_found={len(daily_files)}")
    for file_path in daily_files:
        frame = _load_csv(file_path)
        if frame is None:
            print(f"merge: skipped_empty_file={file_path}")
            continue
        frames.append(_prepare_daily_frame(file_path, frame))

    old_frame = _load_csv(old_features_path)
    if old_frame is not None:
        frames.append(_prepare_historical_frame(old_frame))
        print(f"merge: using_old_features={old_features_path}")
    else:
        print(f"merge: old_features_missing_or_empty={old_features_path}")

    if not frames:
        raise ValueError("No input CSV files found for merge.")

    df = pd.concat(frames, ignore_index=True)
    print(f"merge: rows_concatenated={len(df)}")
    df = _align_columns(df)
    df = _normalize_string_columns(df)

    duplicate_rows = int(df.duplicated().sum())
    duplicate_snapshots = 0
    if all(column in df.columns for column in DEDUPLICATE_COLUMNS):
        complete_keys = df[DEDUPLICATE_COLUMNS].notna().all(axis=1)
        duplicate_snapshots = int(
            df.loc[complete_keys].duplicated(
                subset=DEDUPLICATE_COLUMNS,
                keep="last",
            ).sum()
        )
        deduped_complete = df.loc[complete_keys].drop_duplicates(
            subset=DEDUPLICATE_COLUMNS,
            keep="last",
        )
        df = pd.concat([deduped_complete, df.loc[~complete_keys]], ignore_index=True)

    duplicate_full_rows_removed = int(df.duplicated().sum())
    if duplicate_full_rows_removed:
        df = df.drop_duplicates(keep="last").reset_index(drop=True)

    rows_with_empty_any, rows_with_empty_required, empty_by_column = _empty_summary(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    summary = {
        "rows_in": len(df),
        "duplicate_rows": duplicate_rows,
        "duplicate_snapshots_removed": duplicate_snapshots,
        "duplicate_full_rows_removed": duplicate_full_rows_removed,
        "rows_with_empty_any": rows_with_empty_any,
        "rows_with_empty_required": rows_with_empty_required,
        "empty_by_column": empty_by_column,
        "output": str(output_path),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Merge daily API CSVs with historical features."
    )
    parser.add_argument(
        "--daily-dir",
        default="etl/exports/daily",
        help="Directory with daily CSV files.",
    )
    parser.add_argument(
        "--old-features",
        default="etl/exports/flights_features.csv",
        help="Historical features CSV path.",
    )
    parser.add_argument(
        "--output",
        default="etl/exports/flights_features_all.csv",
        help="Output merged CSV path.",
    )
    args = parser.parse_args()

    daily_dir = Path(args.daily_dir)
    old_features_path = Path(args.old_features)
    output_path = Path(args.output)

    summary = merge_and_clean(daily_dir, old_features_path, output_path)
    print(
        "merged:",
        f"rows_in={summary['rows_in']}",
        f"duplicate_rows={summary['duplicate_rows']}",
        f"duplicate_snapshots_removed={summary['duplicate_snapshots_removed']}",
        f"duplicate_full_rows_removed={summary['duplicate_full_rows_removed']}",
        f"rows_with_empty_any={summary['rows_with_empty_any']}",
        f"rows_with_empty_required={summary['rows_with_empty_required']}",
        f"empty_columns={len(summary['empty_by_column'])}",
        f"output={summary['output']}",
    )
    if summary["empty_by_column"]:
        print(f"merge: empty_by_column={summary['empty_by_column']}")


if __name__ == "__main__":
    main()
