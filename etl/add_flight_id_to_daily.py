from __future__ import annotations

import argparse
import hashlib
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

FILE_DATE_RE = re.compile(
    r"^(?P<prefix>flight|flights)_(?P<date>\d{4}-\d{2}-\d{2}|\d{2}_\d{2}(?:_\d{2})?)\.csv$",
    re.IGNORECASE,
)

# We intentionally exclude price/search-day features so the same flight keeps
# the same id across different snapshots while the fare changes.
FLIGHT_ID_FEATURES = [
    "departure_date",
    "origin",
    "destination",
    "airline",
    "travel_class",
    "trip_type",
    "passengers_total",
    "stops",
    "duration_minutes",
    "depart_hour",
    "departure_time",
    "arrival_time",
]

UPPER_STRING_COLUMNS = {"origin", "destination"}
NUMERIC_COLUMNS = {
    "passengers_total",
    "stops",
    "duration_minutes",
    "depart_hour",
}


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


def _normalize_string_value(value: object, uppercase: bool = False) -> str:
    if pd.isna(value):
        return "na"
    text = str(value).strip()
    if not text:
        return "na"
    text = re.sub(r"\s+", " ", text)
    if uppercase:
        return text.upper()
    return text.lower().replace(" ", "_").replace("-", "_")


def _normalize_travel_class(value: object) -> str:
    if pd.isna(value):
        return "na"
    raw = str(value).strip().lower()
    if not raw:
        return "na"
    if raw in {"1", "economy", "economy class"}:
        return "economy"
    if raw in {"2", "premium", "premium economy", "premium economy class"}:
        return "premium"
    if raw in {"3", "business", "business class"}:
        return "business"
    if raw in {"4", "first", "first class"}:
        return "first"
    if "premium" in raw and "economy" in raw:
        return "premium"
    if "business" in raw:
        return "business"
    if "first" in raw:
        return "first"
    if "economy" in raw:
        return "economy"
    return raw.replace(" ", "_")


def _normalize_trip_type(value: object) -> str:
    if pd.isna(value):
        return "na"
    raw = str(value).strip().lower()
    if not raw:
        return "na"
    if raw in {"1", "round_trip", "round-trip", "round trip"}:
        return "round_trip"
    if raw in {"2", "one_way", "one-way", "one way"}:
        return "one_way"
    if raw in {"3", "multi_city", "multi-city", "multi city"}:
        return "multi_city"
    return raw.replace("-", "_").replace(" ", "_")


def _normalize_time_bucket(value: object) -> str:
    if pd.isna(value):
        return "na"
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return "na"
    mapping = {
        "late_night": "late_night",
        "early_morning": "early_morning",
        "morning": "morning",
        "afternoon": "afternoon",
        "evening": "evening",
        "night": "night",
    }
    return mapping.get(raw, raw)


def _time_bucket_from_hour(hour: object) -> str:
    if pd.isna(hour):
        return "na"
    hour_int = int(float(hour))
    if 0 <= hour_int < 4:
        return "late_night"
    if 4 <= hour_int < 8:
        return "early_morning"
    if 8 <= hour_int < 12:
        return "morning"
    if 12 <= hour_int < 17:
        return "afternoon"
    if 17 <= hour_int < 21:
        return "evening"
    return "night"


def _arrival_bucket_from_departure(depart_hour: object, duration_minutes: object) -> str:
    if pd.isna(depart_hour) or pd.isna(duration_minutes):
        return "na"
    total_minutes = int(float(depart_hour)) * 60 + max(int(float(duration_minutes)), 0)
    arrival_hour = (total_minutes // 60) % 24
    return _time_bucket_from_hour(arrival_hour)


def _normalize_numeric_value(value: object) -> str:
    if pd.isna(value):
        return "na"
    try:
        rounded = float(value)
    except (TypeError, ValueError):
        return "na"
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _normalize_feature_value(feature: str, value: object) -> str:
    if feature in UPPER_STRING_COLUMNS:
        return _normalize_string_value(value, uppercase=True)
    if feature == "departure_date":
        if pd.isna(value):
            return "na"
        try:
            return pd.to_datetime(value, errors="raise").date().isoformat()
        except Exception:
            return "na"
    if feature == "airline":
        return _normalize_string_value(value, uppercase=False)
    if feature == "travel_class":
        return _normalize_travel_class(value)
    if feature == "trip_type":
        return _normalize_trip_type(value)
    if feature in {"departure_time", "arrival_time"}:
        return _normalize_time_bucket(value)
    if feature in NUMERIC_COLUMNS:
        return _normalize_numeric_value(value)
    return _normalize_string_value(value, uppercase=False)


def _ensure_departure_date(frame: pd.DataFrame, search_date: date) -> pd.DataFrame:
    if "departure_date" in frame.columns:
        departure_dates = pd.to_datetime(
            frame["departure_date"], errors="coerce"
        ).dt.date.astype("string")
        frame["departure_date"] = departure_dates
        return frame

    if "days_to_departure" not in frame.columns:
        raise ValueError("Missing both 'departure_date' and 'days_to_departure' columns")

    days_numeric = pd.to_numeric(frame["days_to_departure"], errors="coerce")
    frame["departure_date"] = days_numeric.apply(
        lambda value: (
            (search_date + timedelta(days=int(value))).isoformat()
            if pd.notna(value)
            else pd.NA
        )
    ).astype("string")
    return frame


def _ensure_search_date(frame: pd.DataFrame, search_date: date) -> pd.DataFrame:
    if "search_date" in frame.columns:
        search_dates = pd.to_datetime(
            frame["search_date"], errors="coerce"
        ).dt.date.astype("string")
        missing = search_dates.fillna("").str.strip().eq("")
        if missing.any():
            search_dates.loc[missing] = search_date.isoformat()
        frame["search_date"] = search_dates
        return frame

    frame["search_date"] = search_date.isoformat()
    return frame


def _build_flight_id_values(frame: pd.DataFrame) -> list[str]:
    if "depart_hour" in frame.columns and "departure_time" not in frame.columns:
        frame["departure_time"] = pd.to_numeric(
            frame["depart_hour"], errors="coerce"
        ).apply(_time_bucket_from_hour)
    if (
        "depart_hour" in frame.columns
        and "duration_minutes" in frame.columns
        and "arrival_time" not in frame.columns
    ):
        depart_hour_numeric = pd.to_numeric(frame["depart_hour"], errors="coerce")
        duration_numeric = pd.to_numeric(frame["duration_minutes"], errors="coerce")
        frame["arrival_time"] = [
            _arrival_bucket_from_departure(depart_hour, duration)
            for depart_hour, duration in zip(
                depart_hour_numeric.tolist(),
                duration_numeric.tolist(),
            )
        ]

    normalized_columns: list[list[str]] = []

    for column in FLIGHT_ID_FEATURES:
        if column not in frame.columns:
            frame[column] = pd.NA

        series = frame[column]
        normalized = [
            _normalize_feature_value(column, value) for value in series.tolist()
        ]

        normalized_columns.append(normalized)

    ids: list[str] = []
    for values in zip(*normalized_columns):
        payload = "||".join(f"{key}:{value}" for key, value in zip(FLIGHT_ID_FEATURES, values))
        ids.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
    return ids


def _insert_after(columns: list[str], new_column: str, after_column: str) -> list[str]:
    if new_column in columns:
        columns = [column for column in columns if column != new_column]
    if after_column not in columns:
        return columns + [new_column]
    insert_index = columns.index(after_column) + 1
    return columns[:insert_index] + [new_column] + columns[insert_index:]


def add_flight_id_to_file(path: Path, dry_run: bool = False) -> dict[str, object]:
    frame = pd.read_csv(path)
    search_date = _parse_file_date(path)
    frame = _ensure_search_date(frame, search_date)
    frame = _ensure_departure_date(frame, search_date)
    frame["flight_id"] = _build_flight_id_values(frame)

    column_order = list(frame.columns)
    column_order = _insert_after(column_order, "search_date", "days_to_departure")
    column_order = _insert_after(column_order, "departure_date", "search_date")
    column_order = _insert_after(column_order, "flight_id", "departure_date")
    frame = frame[column_order]

    if not dry_run:
        frame.to_csv(path, index=False)

    unique_ids = int(pd.Series(frame["flight_id"]).nunique(dropna=True))
    return {
        "file": path.name,
        "rows": len(frame),
        "unique_flight_ids": unique_ids,
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
        description="Add stable flight_id values to daily ETL CSV files."
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
        result = add_flight_id_to_file(path, dry_run=args.dry_run)
        mode = "preview" if args.dry_run else "updated"
        print(
            f"{mode}: {result['file']} rows={result['rows']} "
            f"unique_flight_ids={result['unique_flight_ids']} "
            f"search_date={result['search_date']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
