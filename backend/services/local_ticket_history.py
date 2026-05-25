import csv
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from math import sqrt
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import fmean
from threading import Lock
from typing import Any, Optional
from urllib.parse import parse_qs

import pandas as pd

from core import _iso_z, _utc_now
from db.ops import _db_get_latest_prediction
from ml.airline_normalization import normalize_airline_value

_SNAPSHOT_FILE_RE = re.compile(
    r"^(?P<prefix>flight|flights)_(?P<date>\d{4}-\d{2}-\d{2}|\d{2}_\d{2}(?:_\d{2})?)\.csv$",
    re.IGNORECASE,
)
_SNAPSHOT_REQUIRED_COLUMNS = [
    "origin",
    "destination",
    "price",
]
_SNAPSHOT_OPTIONAL_COLUMNS = [
    "airline",
    "travel_class",
    "trip_type",
    "passengers_total",
    "stops",
    "duration_minutes",
    "depart_hour",
    "departure_time",
    "arrival_time",
    "days_to_departure",
    "departure_date",
    "flight_id",
]
_SNAPSHOT_COLUMNS = _SNAPSHOT_REQUIRED_COLUMNS + _SNAPSHOT_OPTIONAL_COLUMNS
_EXACT_LOOKUP_FEATURES = [
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
_WEAK_LOOKUP_FEATURES = [
    "departure_date",
    "origin",
    "destination",
    "airline",
    "travel_class",
    "trip_type",
    "stops",
    "depart_hour",
]
_DATE_ROUTE_LOOKUP_FEATURES = ["departure_date", "origin", "destination"]
_MATCH_MODE_PRIORITY = {
    "file-flight-id": 4,
    "temporary-flight-id": 3,
    "temporary-flight-signature": 2,
}
_FILE_SNAPSHOT_INDEX_CACHE: dict[
    tuple[str, int, int], dict[str, dict[Any, dict[str, Any]]]
] = {}
_FILE_SNAPSHOT_INDEX_LOCK = Lock()
_FILE_PRECISE_MATCH_CACHE: dict[
    tuple[tuple[str, int, int], str], Optional[dict[str, Any]]
] = {}
_FILE_PRECISE_MATCH_LOCK = Lock()
_LOCAL_HISTORY_CACHE: dict[tuple[str, tuple[tuple[str, int, int], ...]], dict[str, Any]] = {}
_LOCAL_HISTORY_LOCK = Lock()
_LOCAL_HISTORY_CACHE_MAX_SIZE = 128


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().upper()
    return raw or None


def _normalize_travel_class(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
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


def _normalize_trip_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in {"1", "round_trip", "round-trip", "round trip"}:
        return "round_trip"
    if raw in {"2", "one_way", "one-way", "one way"}:
        return "one_way"
    if raw in {"3", "multi_city", "multi-city", "multi city"}:
        return "multi_city"
    return raw.replace("-", "_").replace(" ", "_")


def _normalize_airline(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    normalized = normalize_airline_value(value)
    if normalized == "Unknown":
        return None
    raw = normalized.strip().lower()
    return raw or None


def _normalize_time_bucket(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return None
    mapping = {
        "late_night": "late_night",
        "early_morning": "early_morning",
        "morning": "morning",
        "afternoon": "afternoon",
        "evening": "evening",
        "night": "night",
    }
    return mapping.get(raw, raw)


def _time_bucket_from_hour(hour: Optional[int]) -> Optional[str]:
    if hour is None:
        return None
    if 0 <= hour < 4:
        return "late_night"
    if 4 <= hour < 8:
        return "early_morning"
    if 8 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _arrival_bucket_from_departure(
    depart_hour: Optional[int],
    duration_minutes: Optional[int],
) -> Optional[str]:
    if depart_hour is None or duration_minutes is None:
        return None
    total_minutes = depart_hour * 60 + max(duration_minutes, 0)
    arrival_hour = int((total_minutes // 60) % 24)
    return _time_bucket_from_hour(arrival_hour)


def _numeric_lookup_token(value: Any) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "na"
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{float(numeric):.6f}".rstrip("0").rstrip(".")


def _date_lookup_token(value: Any) -> str:
    parsed = value if isinstance(value, date) else _parse_iso_date(value)
    if parsed is None:
        return "na"
    return parsed.isoformat()


def _lookup_token_for_feature(feature: str, value: Any) -> str:
    if feature in {"origin", "destination"}:
        return _normalize_code(value) or "na"
    if feature == "airline":
        return _normalize_airline(value) or "na"
    if feature == "travel_class":
        return _normalize_travel_class(value) or "na"
    if feature == "trip_type":
        return _normalize_trip_type(value) or "na"
    if feature in {"departure_time", "arrival_time"}:
        return _normalize_time_bucket(value) or "na"
    if feature == "departure_date":
        return _date_lookup_token(value)
    if feature in {"passengers_total", "stops", "duration_minutes", "depart_hour"}:
        return _numeric_lookup_token(value)
    if value is None:
        return "na"
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return raw or "na"


def _hash_lookup_values(feature_names: list[str], values: tuple[str, ...]) -> str:
    payload = "||".join(
        f"{feature}:{value}" for feature, value in zip(feature_names, values)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_lookup_id_from_criteria(
    criteria: dict[str, Any],
    feature_names: list[str],
    required_features: list[str],
) -> Optional[str]:
    for feature in required_features:
        if _lookup_token_for_feature(feature, criteria.get(feature)) == "na":
            return None
    values = tuple(
        _lookup_token_for_feature(feature, criteria.get(feature))
        for feature in feature_names
    )
    return _hash_lookup_values(feature_names, values)


def _read_search_params(ticket: dict[str, Any]) -> dict[str, str]:
    raw = ticket.get("searchParams")
    if not raw:
        return {}
    parsed = parse_qs(str(raw), keep_blank_values=False)
    return {
        key: values[-1]
        for key, values in parsed.items()
        if values and values[-1] != ""
    }


def _infer_snapshot_date(path: Path) -> date:
    stat = path.stat()
    modified_local = datetime.fromtimestamp(stat.st_mtime).astimezone()
    match = _SNAPSHOT_FILE_RE.match(path.name)
    if not match:
        return modified_local.date()

    raw_date = match.group("date")
    if "-" in raw_date:
        parsed = _parse_iso_date(raw_date)
        if parsed:
            return parsed

    parts = raw_date.split("_")
    if len(parts) == 3:
        day_part, month_part, year_part = parts
        try:
            return date(2000 + int(year_part), int(month_part), int(day_part))
        except ValueError:
            return modified_local.date()

    if len(parts) == 2:
        day_part, month_part = parts
        try:
            return date(modified_local.year, int(month_part), int(day_part))
        except ValueError:
            return modified_local.date()

    return modified_local.date()


def _iter_snapshot_files() -> list[Path]:
    root = _repo_root()
    search_roots = [
        root,
        root / "data_fetch",
        root / "etl" / "exports" / "daily",
    ]
    found: dict[str, Path] = {}
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.glob("*.csv"):
            if not path.is_file():
                continue
            if not _SNAPSHOT_FILE_RE.match(path.name):
                continue
            found[str(path.resolve())] = path
    return sorted(
        found.values(),
        key=lambda item: item.stat().st_mtime,
    )


def _file_cache_key(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _prune_snapshot_index_cache(snapshot_files: list[Path]) -> None:
    valid_keys = {_file_cache_key(path) for path in snapshot_files}
    with _FILE_SNAPSHOT_INDEX_LOCK:
        stale_keys = [
            key for key in _FILE_SNAPSHOT_INDEX_CACHE.keys() if key not in valid_keys
        ]
        for key in stale_keys:
            _FILE_SNAPSHOT_INDEX_CACHE.pop(key, None)
    with _FILE_PRECISE_MATCH_LOCK:
        stale_precise_keys = [
            key for key in _FILE_PRECISE_MATCH_CACHE.keys() if key[0] not in valid_keys
        ]
        for key in stale_precise_keys:
            _FILE_PRECISE_MATCH_CACHE.pop(key, None)


def _relative_snapshot_path(path: Path) -> str:
    root = _repo_root()
    try:
        relative_path = str(path.resolve().relative_to(root))
    except ValueError:
        relative_path = str(path.resolve())
    return relative_path.replace("\\", "/")


def _read_csv_header(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            return next(reader, [])
    except OSError:
        return []


def _build_departure_dates_from_days(
    days_to_departure: pd.Series,
    search_date: date,
) -> pd.Series:
    days_numeric = pd.to_numeric(days_to_departure, errors="coerce")
    return days_numeric.apply(
        lambda value: (
            search_date + timedelta(days=int(value))
            if pd.notna(value)
            else pd.NaT
        )
    )


def _prepare_snapshot_frame(
    path: Path,
    snapshot_day: date,
    requested_columns: Optional[list[str]] = None,
    route_key: Optional[tuple[str, str]] = None,
) -> Optional[pd.DataFrame]:
    desired_columns = requested_columns or _SNAPSHOT_COLUMNS
    available_columns = [
        column for column in desired_columns if column in _read_csv_header(path)
    ]
    if not set(_SNAPSHOT_REQUIRED_COLUMNS).issubset(available_columns):
        return None

    try:
        if route_key:
            chunks: list[pd.DataFrame] = []
            for chunk in pd.read_csv(
                path,
                usecols=available_columns,
                encoding="utf-8-sig",
                low_memory=False,
                chunksize=50_000,
            ):
                if chunk.empty:
                    continue
                origins = chunk["origin"].astype("string").str.strip().str.upper()
                destinations = chunk["destination"].astype("string").str.strip().str.upper()
                route_mask = (origins == route_key[0]) & (destinations == route_key[1])
                if route_mask.any():
                    chunks.append(chunk.loc[route_mask].copy())
            if not chunks:
                return None
            frame = pd.concat(chunks, ignore_index=True)
        else:
            frame = pd.read_csv(
                path,
                usecols=available_columns,
                encoding="utf-8-sig",
                low_memory=False,
            )
    except ValueError:
        return None

    if frame.empty:
        return None

    frame["origin"] = frame["origin"].astype("string").str.strip().str.upper()
    frame["destination"] = frame["destination"].astype("string").str.strip().str.upper()
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["origin", "destination", "price"])
    if route_key:
        frame = frame[
            (frame["origin"] == route_key[0]) & (frame["destination"] == route_key[1])
        ]
    if frame.empty:
        return None

    airline_display = (
        frame["airline"].astype("string").fillna("").map(normalize_airline_value)
        if "airline" in frame.columns
        else pd.Series("", index=frame.index, dtype="string")
    )
    travel_class_raw = (
        frame["travel_class"]
        if "travel_class" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    trip_type_raw = (
        frame["trip_type"]
        if "trip_type" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    passengers_raw = (
        frame["passengers_total"]
        if "passengers_total" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    stops_raw = (
        frame["stops"]
        if "stops" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    duration_raw = (
        frame["duration_minutes"]
        if "duration_minutes" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    depart_hour_numeric = pd.to_numeric(
        frame["depart_hour"], errors="coerce"
    ) if "depart_hour" in frame.columns else pd.Series(
        [float("nan")] * len(frame), index=frame.index, dtype="float64"
    )
    duration_numeric = pd.to_numeric(
        duration_raw, errors="coerce"
    ) if "duration_minutes" in frame.columns else pd.Series(
        [float("nan")] * len(frame), index=frame.index, dtype="float64"
    )
    departure_time_raw = (
        frame["departure_time"]
        if "departure_time" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    arrival_time_raw = (
        frame["arrival_time"]
        if "arrival_time" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="object")
    )
    if "departure_date" in frame.columns:
        departure_dates = pd.to_datetime(
            frame["departure_date"], errors="coerce"
        ).dt.date
    elif "days_to_departure" in frame.columns:
        departure_dates = _build_departure_dates_from_days(
            frame["days_to_departure"], snapshot_day
        )
    else:
        departure_dates = pd.Series(pd.NaT, index=frame.index, dtype="object")

    derived_departure_time = depart_hour_numeric.apply(
        lambda value: _time_bucket_from_hour(_to_int(value))
    )
    derived_arrival_time = pd.Series(
        [
            _arrival_bucket_from_departure(_to_int(hour), _to_int(duration))
            for hour, duration in zip(depart_hour_numeric.tolist(), duration_numeric.tolist())
        ],
        index=frame.index,
        dtype="object",
    )

    frame["_airline_display"] = airline_display
    frame["airline"] = airline_display.map(
        lambda value: _lookup_token_for_feature("airline", value)
    )
    frame["travel_class"] = travel_class_raw.map(
        lambda value: _lookup_token_for_feature("travel_class", value)
    )
    frame["trip_type"] = trip_type_raw.map(
        lambda value: _lookup_token_for_feature("trip_type", value)
    )
    frame["passengers_total"] = passengers_raw.map(
        lambda value: _lookup_token_for_feature("passengers_total", value)
    )
    frame["stops"] = stops_raw.map(
        lambda value: _lookup_token_for_feature("stops", value)
    )
    frame["duration_minutes"] = duration_raw.map(
        lambda value: _lookup_token_for_feature("duration_minutes", value)
    )
    frame["depart_hour"] = depart_hour_numeric.map(
        lambda value: _lookup_token_for_feature("depart_hour", value)
    )
    frame["departure_time"] = departure_time_raw.combine_first(
        derived_departure_time
    ).map(lambda value: _lookup_token_for_feature("departure_time", value))
    frame["arrival_time"] = arrival_time_raw.combine_first(
        derived_arrival_time
    ).map(lambda value: _lookup_token_for_feature("arrival_time", value))
    frame["departure_date"] = departure_dates.map(
        lambda value: _lookup_token_for_feature("departure_date", value)
    )
    if "flight_id" in frame.columns:
        frame["flight_id"] = (
            frame["flight_id"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lower()
            .replace({"": "na", "nan": "na", "<na>": "na"})
        )
    else:
        frame["flight_id"] = "na"

    frame = frame[(frame["origin"] != "na") & (frame["destination"] != "na")]
    if frame.empty:
        return None
    return frame


def _build_point_from_group(
    group: pd.DataFrame,
    snapshot_day: date,
    source_file: str,
    match_mode: str,
) -> dict[str, Any]:
    prices = group["price"]
    point_dt = datetime.combine(snapshot_day, time(12, 0, tzinfo=timezone.utc))
    airlines = sorted(
        {
            airline
            for airline in group["_airline_display"].tolist()
            if isinstance(airline, str) and airline.strip()
        }
    )
    return {
        "ts": _iso_z(point_dt),
        "price": round(float(prices.mean()), 2),
        "minPrice": round(float(prices.min()), 2),
        "maxPrice": round(float(prices.max()), 2),
        "sampleCount": int(prices.count()),
        "sourceDate": snapshot_day.isoformat(),
        "sourceFile": source_file,
        "matchMode": match_mode,
        "airlines": airlines[:4],
        "isForecast": False,
    }


def _build_grouped_point_index(
    frame: pd.DataFrame,
    group_columns: list[str],
    snapshot_day: date,
    source_file: str,
    match_mode: str,
    key_builder,
) -> dict[Any, dict[str, Any]]:
    if frame.empty:
        return {}

    grouped_index: dict[Any, dict[str, Any]] = {}
    for raw_group_key, group in frame.groupby(group_columns, sort=False, dropna=False):
        key_tuple = raw_group_key if isinstance(raw_group_key, tuple) else (raw_group_key,)
        index_key = key_builder(key_tuple)
        if index_key is None:
            continue
        grouped_index[index_key] = _build_point_from_group(
            group=group,
            snapshot_day=snapshot_day,
            source_file=source_file,
            match_mode=match_mode,
        )
    return grouped_index


def _tuple_key_builder(values: tuple[Any, ...]) -> Optional[tuple[str, ...]]:
    key = tuple(str(value) for value in values)
    if any(value == "na" for value in key):
        return None
    return key


def _single_value_key_builder(values: tuple[Any, ...]) -> Optional[str]:
    if not values:
        return None
    value = str(values[0])
    if not value or value == "na":
        return None
    return value


def _hashed_key_builder(feature_names: list[str]):
    def build(values: tuple[Any, ...]) -> str:
        normalized_values = tuple(str(value) for value in values)
        return _hash_lookup_values(feature_names, normalized_values)

    return build


def _build_snapshot_index_bundle(
    path: Path,
) -> dict[str, dict[Any, dict[str, Any]]]:
    snapshot_day = _infer_snapshot_date(path)
    source_file = _relative_snapshot_path(path)
    frame = _prepare_snapshot_frame(
        path,
        snapshot_day,
        requested_columns=["origin", "destination", "price", "airline"],
    )
    if frame is None or frame.empty:
        return {"route_index": {}}

    return {
        "route_index": _build_grouped_point_index(
            frame=frame,
            group_columns=["origin", "destination"],
            snapshot_day=snapshot_day,
            source_file=source_file,
            match_mode="route-only-from-files-disabled",
            key_builder=_tuple_key_builder,
        ),
    }


def _get_snapshot_index_bundle(
    path: Path,
) -> dict[str, dict[Any, dict[str, Any]]]:
    cache_key = _file_cache_key(path)
    with _FILE_SNAPSHOT_INDEX_LOCK:
        cached = _FILE_SNAPSHOT_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached

    snapshot_bundle = _build_snapshot_index_bundle(path)
    path_key = str(path.resolve())
    with _FILE_SNAPSHOT_INDEX_LOCK:
        stale_versions = [
            key
            for key in _FILE_SNAPSHOT_INDEX_CACHE.keys()
            if key[0] == path_key and key != cache_key
        ]
        for key in stale_versions:
            _FILE_SNAPSHOT_INDEX_CACHE.pop(key, None)
        _FILE_SNAPSHOT_INDEX_CACHE[cache_key] = snapshot_bundle
        return _FILE_SNAPSHOT_INDEX_CACHE[cache_key]


def _best_match_mode(day_points: list[dict[str, Any]]) -> Optional[str]:
    if not day_points:
        return None
    return max(
        (
            str(point.get("matchMode") or "precise-flight-match")
            for point in day_points
        ),
        key=lambda mode: _MATCH_MODE_PRIORITY.get(mode, -1),
    )


def _build_ticket_criteria(ticket: dict[str, Any]) -> dict[str, Any]:
    params = _read_search_params(ticket)
    depart_dt = _parse_iso_datetime(ticket.get("departAt"))
    outbound_date = _parse_iso_date(params.get("outbound_date"))
    departure_date = depart_dt.date() if depart_dt else outbound_date

    passengers = _to_int(ticket.get("passengers"))
    if passengers is None:
        passengers = sum(
            part
            for part in [
                _to_int(params.get("adults")) or 0,
                _to_int(params.get("children")) or 0,
                _to_int(params.get("infants_in_seat")) or 0,
                _to_int(params.get("infants_on_lap")) or 0,
            ]
        )
        if passengers == 0:
            passengers = None

    depart_hour = depart_dt.hour if depart_dt else None
    duration_minutes = _to_int(ticket.get("durationMinutes"))

    criteria = {
        "origin": _normalize_code(ticket.get("origin") or params.get("departure_id")),
        "destination": _normalize_code(
            ticket.get("destination") or params.get("arrival_id")
        ),
        "departure_date": departure_date,
        "depart_hour": depart_hour,
        "departure_time": _time_bucket_from_hour(depart_hour),
        "arrival_time": _arrival_bucket_from_departure(depart_hour, duration_minutes),
        "travel_class": _normalize_travel_class(
            ticket.get("travelClass") or params.get("travel_class")
        ),
        "trip_type": _normalize_trip_type(
            ticket.get("tripType") or params.get("type")
        ),
        "passengers": passengers,
        "passengers_total": passengers,
        "stops": _to_int(ticket.get("stops")),
        "duration_minutes": duration_minutes,
        "airline": _normalize_airline(ticket.get("airline")),
        "currency": str(ticket.get("currency") or params.get("currency") or "USD"),
        "prediction_flight_id": str(ticket.get("flightId") or "").strip() or None,
    }
    criteria["lookup_flight_id"] = _build_lookup_id_from_criteria(
        criteria=criteria,
        feature_names=_EXACT_LOOKUP_FEATURES,
        required_features=[
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
        ],
    )
    criteria["lookup_signature_id"] = _build_lookup_id_from_criteria(
        criteria=criteria,
        feature_names=_WEAK_LOOKUP_FEATURES,
        required_features=[
            "departure_date",
            "origin",
            "destination",
            "airline",
            "stops",
            "depart_hour",
        ],
    )
    if criteria.get("departure_date") and criteria.get("origin") and criteria.get("destination"):
        criteria["lookup_date_route_key"] = (
            criteria["departure_date"].isoformat(),
            criteria["origin"],
            criteria["destination"],
        )
    else:
        criteria["lookup_date_route_key"] = None
    if criteria.get("origin") and criteria.get("destination"):
        criteria["lookup_route_key"] = (
            criteria["origin"],
            criteria["destination"],
        )
    else:
        criteria["lookup_route_key"] = None
    return criteria


def _clone_point(point: dict[str, Any]) -> dict[str, Any]:
    return {
        **point,
        "airlines": list(point.get("airlines") or []),
    }


def _history_cache_token(criteria: dict[str, Any]) -> str:
    parts = [
        str(criteria.get("origin") or ""),
        str(criteria.get("destination") or ""),
        criteria["departure_date"].isoformat()
        if isinstance(criteria.get("departure_date"), date)
        else str(criteria.get("departure_date") or ""),
        str(criteria.get("airline") or ""),
        str(criteria.get("travel_class") or ""),
        str(criteria.get("trip_type") or ""),
        str(criteria.get("passengers_total") or ""),
        str(criteria.get("stops") or ""),
        str(criteria.get("duration_minutes") or ""),
        str(criteria.get("depart_hour") or ""),
        str(criteria.get("lookup_flight_id") or ""),
        str(criteria.get("lookup_signature_id") or ""),
        str(criteria.get("prediction_flight_id") or ""),
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def _snapshot_signature(snapshot_files: list[Path]) -> tuple[tuple[str, int, int], ...]:
    return tuple(_file_cache_key(path) for path in snapshot_files)


def _build_precise_match_cache_token(criteria: dict[str, Any]) -> str:
    parts = [
        str(criteria.get("lookup_flight_id") or ""),
        str(criteria.get("lookup_signature_id") or ""),
        "|".join(criteria.get("lookup_date_route_key") or ()),
        "|".join(criteria.get("lookup_route_key") or ()),
    ]
    return "||".join(parts)


def _find_precise_point_in_file(
    path: Path,
    criteria: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not any(
        [
            criteria.get("lookup_flight_id"),
            criteria.get("lookup_signature_id"),
            criteria.get("lookup_date_route_key"),
        ]
    ):
        return None

    snapshot_day = _infer_snapshot_date(path)
    departure_date = criteria.get("departure_date")
    if departure_date and snapshot_day > departure_date:
        return None

    route_key = criteria.get("lookup_route_key")
    cache_key = (_file_cache_key(path), _build_precise_match_cache_token(criteria))
    with _FILE_PRECISE_MATCH_LOCK:
        if cache_key in _FILE_PRECISE_MATCH_CACHE:
            cached = _FILE_PRECISE_MATCH_CACHE[cache_key]
            return _clone_point(cached) if cached is not None else None
    source_file = _relative_snapshot_path(path)
    frame = _prepare_snapshot_frame(
        path,
        snapshot_day,
        requested_columns=_SNAPSHOT_COLUMNS,
        route_key=route_key,
    )
    if frame is None or frame.empty:
        with _FILE_PRECISE_MATCH_LOCK:
            _FILE_PRECISE_MATCH_CACHE[cache_key] = None
        return None

    date_route_frame = frame
    lookup_date_route_key = criteria.get("lookup_date_route_key")
    if lookup_date_route_key:
        date_route_frame = frame[
            frame["departure_date"] == lookup_date_route_key[0]
        ]

    lookup_flight_id = criteria.get("lookup_flight_id")
    if lookup_flight_id and not date_route_frame.empty:
        file_id_frame = date_route_frame[date_route_frame["flight_id"] == lookup_flight_id]
        if not file_id_frame.empty:
            point = _build_point_from_group(
                group=file_id_frame,
                snapshot_day=snapshot_day,
                source_file=source_file,
                match_mode="file-flight-id",
            )
            with _FILE_PRECISE_MATCH_LOCK:
                _FILE_PRECISE_MATCH_CACHE[cache_key] = point
            return _clone_point(point)

        temporary_flight_id_index = _build_grouped_point_index(
            frame=date_route_frame,
            group_columns=_EXACT_LOOKUP_FEATURES,
            snapshot_day=snapshot_day,
            source_file=source_file,
            match_mode="temporary-flight-id",
            key_builder=_hashed_key_builder(_EXACT_LOOKUP_FEATURES),
        )
        point = temporary_flight_id_index.get(lookup_flight_id)
        if point:
            with _FILE_PRECISE_MATCH_LOCK:
                _FILE_PRECISE_MATCH_CACHE[cache_key] = point
            return _clone_point(point)

    lookup_signature_id = criteria.get("lookup_signature_id")
    if lookup_signature_id and not date_route_frame.empty:
        temporary_signature_index = _build_grouped_point_index(
            frame=date_route_frame,
            group_columns=_WEAK_LOOKUP_FEATURES,
            snapshot_day=snapshot_day,
            source_file=source_file,
            match_mode="temporary-flight-signature",
            key_builder=_hashed_key_builder(_WEAK_LOOKUP_FEATURES),
        )
        point = temporary_signature_index.get(lookup_signature_id)
        if point:
            with _FILE_PRECISE_MATCH_LOCK:
                _FILE_PRECISE_MATCH_CACHE[cache_key] = point
            return _clone_point(point)

    with _FILE_PRECISE_MATCH_LOCK:
        _FILE_PRECISE_MATCH_CACHE[cache_key] = None
    return None


def _scan_snapshot_file(path: Path, criteria: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not criteria.get("lookup_route_key"):
        return None

    precise_point = _find_precise_point_in_file(path, criteria)
    if precise_point:
        return precise_point
    return None


def _generate_forecast_points(
    actual_points: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    if not actual_points:
        return [], None

    latest_actual = actual_points[-1]
    latest_dt = _parse_iso_datetime(latest_actual.get("ts"))
    if latest_dt is None:
        return [], None

    departure_date = criteria.get("departure_date")
    steps = 3
    if departure_date and departure_date > latest_dt.date():
        steps = min(max((departure_date - latest_dt.date()).days, 1), 7)

    prediction = None
    prediction_flight_id = criteria.get("prediction_flight_id")
    if prediction_flight_id:
        prediction = _db_get_latest_prediction(prediction_flight_id)

    if prediction and prediction.get("predicted_price") is not None:
        predicted_price = float(prediction["predicted_price"])
        horizon_days = int(prediction.get("horizon_days") or steps or 1)
        target_dt = latest_dt + timedelta(days=max(horizon_days, 1))
        if departure_date and target_dt.date() > departure_date:
            target_dt = datetime.combine(departure_date, latest_dt.timetz()).astimezone(
                latest_dt.tzinfo
            )
        total_days = max((target_dt.date() - latest_dt.date()).days, 1)
        start_price = float(latest_actual["price"])
        lower = (
            float(prediction["lower"])
            if prediction.get("lower") is not None
            else None
        )
        upper = (
            float(prediction["upper"])
            if prediction.get("upper") is not None
            else None
        )
        points: list[dict[str, Any]] = []
        for day_idx in range(1, total_days + 1):
            ratio = day_idx / total_days
            point_dt = latest_dt + timedelta(days=day_idx)
            point: dict[str, Any] = {
                "ts": _iso_z(point_dt),
                "price": round(start_price + (predicted_price - start_price) * ratio, 2),
                "isForecast": True,
            }
            if lower is not None:
                point["lower"] = round(start_price + (lower - start_price) * ratio, 2)
            if upper is not None:
                point["upper"] = round(start_price + (upper - start_price) * ratio, 2)
            points.append(point)

        return (
            points,
            {
                "source": "ml-ensemble",
                "modelName": prediction.get("model_name") or "ml-ensemble",
                "generatedAt": _iso_z(prediction["created_at"]),
                "horizonDays": total_days,
            },
        )

    if len(actual_points) < 2:
        return [], None

    actual_dates = [
        _parse_iso_datetime(point.get("ts"))
        for point in actual_points
    ]
    if any(item is None for item in actual_dates):
        return [], None

    first_dt = actual_dates[0]
    xs = [
        (item - first_dt).total_seconds() / 86400
        for item in actual_dates
        if item is not None
    ]
    ys = [float(point["price"]) for point in actual_points]
    if len(xs) < 2 or len(xs) != len(ys):
        return [], None

    x_mean = fmean(xs)
    y_mean = fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = 0.0 if denominator == 0 else sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)
    ) / denominator
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    uncertainty = (
        sqrt(sum((value - fmean(residuals)) ** 2 for value in residuals) / len(residuals))
        if len(residuals) > 1
        else max(y_mean * 0.05, 5.0)
    )

    forecast_points: list[dict[str, Any]] = []
    for day_idx in range(1, steps + 1):
        point_dt = latest_dt + timedelta(days=day_idx)
        x_value = (point_dt - first_dt).total_seconds() / 86400
        predicted_price = max(intercept + slope * x_value, 1.0)
        forecast_points.append(
            {
                "ts": _iso_z(point_dt),
                "price": round(predicted_price, 2),
                "lower": round(max(predicted_price - uncertainty, 1.0), 2),
                "upper": round(predicted_price + uncertainty, 2),
                "isForecast": True,
            }
        )

    return (
        forecast_points,
        {
            "source": "local-linear-trend",
            "modelName": "local-linear-trend",
            "generatedAt": _iso_z(_utc_now()),
            "horizonDays": steps,
        },
    )


def recent_price_trend_per_day_from_points(actual_points: list[dict[str, Any]]) -> float:
    if len(actual_points) < 2:
        return 0.0
    latest = actual_points[-1]
    previous = actual_points[-2]
    latest_dt = _parse_iso_datetime(latest.get("ts"))
    previous_dt = _parse_iso_datetime(previous.get("ts"))
    if latest_dt is None or previous_dt is None:
        return 0.0
    day_delta = (latest_dt - previous_dt).total_seconds() / 86400
    if day_delta <= 0:
        return 0.0
    try:
        price_delta = float(latest["price"]) - float(previous["price"])
    except (TypeError, ValueError):
        return 0.0
    trend = price_delta / day_delta
    return round(max(min(trend, 500.0), -500.0), 4)


def estimate_ticket_price_trend_per_day(ticket: dict[str, Any]) -> float:
    history = build_local_ticket_history(ticket, max_snapshot_files=4)
    return recent_price_trend_per_day_from_points(history.get("actual") or [])


def build_local_ticket_history(
    ticket: dict[str, Any],
    max_snapshot_files: Optional[int] = None,
) -> dict[str, Any]:
    criteria = _build_ticket_criteria(ticket)
    snapshot_files = _iter_snapshot_files()
    if max_snapshot_files is not None and max_snapshot_files > 0:
        snapshot_files = snapshot_files[-max_snapshot_files:]
    _prune_snapshot_index_cache(snapshot_files)
    cache_key = (_history_cache_token(criteria), _snapshot_signature(snapshot_files))
    with _LOCAL_HISTORY_LOCK:
        cached = _LOCAL_HISTORY_CACHE.get(cache_key)
    if cached is not None:
        return deepcopy(cached)

    actual_points_raw: list[dict[str, Any]] = []

    max_workers = min(6, len(snapshot_files)) if snapshot_files else 0
    if max_workers <= 1:
        for path in snapshot_files:
            point = _scan_snapshot_file(path, criteria)
            if point:
                actual_points_raw.append(point)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for point in executor.map(
                lambda snapshot_path: _scan_snapshot_file(snapshot_path, criteria),
                snapshot_files,
            ):
                if point:
                    actual_points_raw.append(point)

    grouped_by_day: dict[str, list[dict[str, Any]]] = {}
    for point in actual_points_raw:
        grouped_by_day.setdefault(point["sourceDate"], []).append(point)

    actual_points: list[dict[str, Any]] = []
    for source_date, day_points in grouped_by_day.items():
        prices = [float(point["price"]) for point in day_points]
        sample_count = sum(int(point.get("sampleCount") or 0) for point in day_points)
        files = sorted(
            {str(point.get("sourceFile")) for point in day_points if point.get("sourceFile")}
        )
        airlines = sorted(
            {
                airline
                for point in day_points
                for airline in (point.get("airlines") or [])
            }
        )
        day_dt = datetime.combine(
            date.fromisoformat(source_date),
            time(12, 0, tzinfo=timezone.utc),
        )
        actual_points.append(
            {
                "ts": _iso_z(day_dt),
                "price": round(fmean(prices), 2),
                "minPrice": round(min(float(point["minPrice"]) for point in day_points), 2),
                "maxPrice": round(max(float(point["maxPrice"]) for point in day_points), 2),
                "sampleCount": sample_count,
                "sourceDate": source_date,
                "sourceFile": ", ".join(files),
                "matchMode": _best_match_mode(day_points) or "precise-flight-match",
                "airlines": airlines[:6],
                "isForecast": False,
            }
        )

    actual_points.sort(key=lambda item: item["ts"])
    forecast_points, forecast_meta = _generate_forecast_points(actual_points, criteria)

    prices = [float(point["price"]) for point in actual_points]
    available_days = sorted({point["sourceDate"] for point in actual_points})

    summary = {
        "filesScanned": len(snapshot_files),
        "matchedSnapshots": len(actual_points_raw),
        "matchedDays": len(available_days),
        "availableDays": available_days,
        "departureDate": criteria["departure_date"].isoformat()
        if criteria.get("departure_date")
        else None,
        "latestPrice": round(prices[-1], 2) if prices else None,
        "minPrice": round(min(prices), 2) if prices else None,
        "maxPrice": round(max(prices), 2) if prices else None,
        "averagePrice": round(fmean(prices), 2) if prices else None,
        "lastCapturedAt": actual_points[-1]["ts"] if actual_points else None,
    }

    result = {
        "ticketId": ticket.get("id"),
        "currency": criteria["currency"],
        "actual": actual_points,
        "forecast": forecast_points,
        "forecastMeta": forecast_meta,
        "summary": summary,
        "matching": {
            "origin": criteria.get("origin"),
            "destination": criteria.get("destination"),
            "travelClass": criteria.get("travel_class"),
            "tripType": criteria.get("trip_type"),
            "passengers": criteria.get("passengers"),
            "lookupFlightId": criteria.get("lookup_flight_id"),
            "lookupSignatureId": criteria.get("lookup_signature_id"),
            "strategy": (
                "Search order: CSV flight_id -> temporary exact flight id -> "
                "temporary weak signature. Route-only fallback is disabled."
            ),
        },
    }
    with _LOCAL_HISTORY_LOCK:
        if len(_LOCAL_HISTORY_CACHE) >= _LOCAL_HISTORY_CACHE_MAX_SIZE:
            oldest_key = next(iter(_LOCAL_HISTORY_CACHE))
            _LOCAL_HISTORY_CACHE.pop(oldest_key, None)
        _LOCAL_HISTORY_CACHE[cache_key] = deepcopy(result)
    return result
