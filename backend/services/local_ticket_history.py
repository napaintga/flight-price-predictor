from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from math import sqrt
from pathlib import Path
from statistics import fmean
from threading import Lock
from typing import Any, Optional
from urllib.parse import parse_qs

import pandas as pd

from core import _iso_z, _utc_now
from ml.airline_normalization import normalize_airline_value
from services.flight_price_model import predict_flight_price

FEATURES_FILE_NAME = "flights_features_all.csv"
REQUIRED_COLUMNS = ["search_date", "departure_date", "origin", "destination", "price"]
OPTIONAL_COLUMNS = [
    "flight_id",
    "airline",
    "travel_class",
    "passengers_total",
    "trip_type",
    "stops",
    "duration_minutes",
    "depart_hour",
    "departure_time",
    "arrival_time",
    "distance_km",
    "days_to_departure",
]
READ_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

_HISTORY_CACHE: dict[tuple[str, tuple[str, int, int]], dict[str, Any]] = {}
_HISTORY_LOCK = Lock()
_HISTORY_CACHE_MAX_SIZE = 128


def _repo_root() -> Path:
    backend_root = Path(__file__).resolve().parents[1]
    return Path(os.getenv("PROJECT_ROOT") or backend_root.parent).resolve()


def _features_file() -> Path:
    return _repo_root() / "etl" / "exports" / FEATURES_FILE_NAME


def _file_cache_key(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
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
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if pd.notna(parsed) else None


def _normalize_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).split(",")[0].strip().upper()
    return raw or None


def _normalize_airline(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    normalized = normalize_airline_value(value)
    if normalized == "Unknown":
        return None
    return normalized.strip().lower() or None


def _normalize_travel_class(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in {"1", "economy", "economy class"}:
        return "economy class"
    if raw in {"2", "premium", "premium economy", "premium economy class"}:
        return "premium economy"
    if raw in {"3", "business", "business class"}:
        return "business class"
    if raw in {"4", "first", "first class"}:
        return "first class"
    return raw.replace("_", " ")


def _normalize_trip_type(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return None
    if raw in {"1", "round_trip", "roundtrip"}:
        return "round_trip"
    if raw in {"2", "one_way", "oneway"}:
        return "one_way"
    if raw in {"3", "multi_city", "multicity"}:
        return "multi_city"
    return raw


def _time_bucket_from_hour(hour: Optional[int]) -> Optional[str]:
    if hour is None:
        return None
    if 0 <= hour < 5:
        return "night"
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


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


def _ticket_departure_date(ticket: dict[str, Any], params: dict[str, str]) -> Optional[date]:
    return (
        _parse_iso_date(ticket.get("departAt"))
        or _parse_iso_date(ticket.get("departureDate"))
        or _parse_iso_date(params.get("outbound_date"))
    )


def _build_ticket_criteria(ticket: dict[str, Any]) -> dict[str, Any]:
    params = _read_search_params(ticket)
    passengers = (
        _to_int(ticket.get("passengers"))
        or _to_int(ticket.get("passengers_total"))
        or sum(
            _to_int(params.get(key)) or 0
            for key in ("adults", "children", "infants_in_seat", "infants_on_lap")
        )
        or None
    )
    depart_hour = _to_int(ticket.get("departHour"))
    if depart_hour is None:
        depart_dt = _parse_iso_datetime(ticket.get("departAt"))
        depart_hour = depart_dt.hour if depart_dt else None

    return {
        "origin": _normalize_code(ticket.get("origin") or params.get("departure_id")),
        "destination": _normalize_code(ticket.get("destination") or params.get("arrival_id")),
        "departure_date": _ticket_departure_date(ticket, params),
        "airline": _normalize_airline(ticket.get("airline")),
        "travel_class": _normalize_travel_class(ticket.get("travelClass") or params.get("travel_class")),
        "trip_type": _normalize_trip_type(ticket.get("tripType") or params.get("type")),
        "passengers": passengers,
        "passengers_total": passengers,
        "stops": _to_int(ticket.get("stops")),
        "duration_minutes": _to_int(ticket.get("durationMinutes")),
        "depart_hour": depart_hour,
        "currency": str(ticket.get("currency") or params.get("currency") or "USD"),
        "flight_id": str(ticket.get("flightId") or ticket.get("id") or "").strip() or None,
        "search_params": params,
    }


def _history_cache_token(criteria: dict[str, Any]) -> str:
    parts = [
        str(criteria.get("origin") or ""),
        str(criteria.get("destination") or ""),
        criteria["departure_date"].isoformat()
        if isinstance(criteria.get("departure_date"), date)
        else "",
        str(criteria.get("airline") or ""),
        str(criteria.get("travel_class") or ""),
        str(criteria.get("trip_type") or ""),
        str(criteria.get("passengers_total") or ""),
        str(criteria.get("stops") or ""),
        str(criteria.get("duration_minutes") or ""),
        str(criteria.get("depart_hour") or ""),
        str(criteria.get("flight_id") or ""),
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


@lru_cache(maxsize=8)
def _read_header(path_text: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    del mtime_ns, size
    return tuple(pd.read_csv(path_text, nrows=0).columns.tolist())


def _available_columns(path: Path) -> list[str]:
    path_text, mtime_ns, size = _file_cache_key(path)
    header = set(_read_header(path_text, mtime_ns, size))
    if not set(REQUIRED_COLUMNS).issubset(header):
        return []
    return [column for column in READ_COLUMNS if column in header]


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    frame = chunk.copy()
    frame["origin"] = frame["origin"].astype("string").str.strip().str.upper()
    frame["destination"] = frame["destination"].astype("string").str.strip().str.upper()
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["search_date"] = pd.to_datetime(frame["search_date"], errors="coerce").dt.date
    frame["departure_date"] = pd.to_datetime(frame["departure_date"], errors="coerce").dt.date
    if "airline" in frame.columns:
        frame["_airline_display"] = frame["airline"].map(normalize_airline_value)
        frame["_airline_key"] = frame["_airline_display"].map(_normalize_airline)
    else:
        frame["_airline_display"] = ""
        frame["_airline_key"] = None
    if "travel_class" in frame.columns:
        frame["_travel_class_key"] = frame["travel_class"].map(_normalize_travel_class)
    else:
        frame["_travel_class_key"] = None
    if "trip_type" in frame.columns:
        frame["_trip_type_key"] = frame["trip_type"].map(_normalize_trip_type)
    else:
        frame["_trip_type_key"] = None
    for column in ("passengers_total", "stops", "duration_minutes", "depart_hour"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["origin", "destination", "price", "search_date"])


def _filter_matches(frame: pd.DataFrame, criteria: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    route = frame[
        (frame["origin"] == criteria.get("origin"))
        & (frame["destination"] == criteria.get("destination"))
    ].copy()
    if route.empty:
        return route, "no-route-match"

    filtered = route
    match_parts = ["route"]
    optional_filters = [
        ("departure_date", criteria.get("departure_date")),
        ("_airline_key", criteria.get("airline")),
        ("_travel_class_key", criteria.get("travel_class")),
        ("_trip_type_key", criteria.get("trip_type")),
        ("passengers_total", criteria.get("passengers_total")),
        ("stops", criteria.get("stops")),
        ("duration_minutes", criteria.get("duration_minutes")),
        ("depart_hour", criteria.get("depart_hour")),
    ]
    for column, value in optional_filters:
        if value is None or column not in filtered.columns:
            continue
        if column == "departure_date":
            candidate = filtered[filtered[column] == value]
            if "search_date" in candidate.columns:
                candidate = candidate[candidate["search_date"] <= value]
            if candidate.empty:
                return candidate, "+".join(match_parts)
        elif column in {"_airline_key", "_travel_class_key", "_trip_type_key"}:
            candidate = filtered[filtered[column] == value]
        else:
            candidate = filtered[filtered[column].round().astype("Int64") == int(value)]
        if candidate.empty:
            continue
        filtered = candidate
        match_parts.append(column.replace("_key", "").strip("_"))

    return filtered, "+".join(match_parts)


def _read_matching_frame(path: Path, criteria: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    columns = _available_columns(path)
    if not columns or not criteria.get("origin") or not criteria.get("destination"):
        return pd.DataFrame(), "missing-required-data"

    chunks: list[pd.DataFrame] = []
    match_mode = "route"
    for chunk in pd.read_csv(
        path,
        usecols=columns,
        encoding="utf-8-sig",
        low_memory=False,
        chunksize=100_000,
    ):
        prepared = _prepare_chunk(chunk)
        matched, chunk_mode = _filter_matches(prepared, criteria)
        if not matched.empty:
            chunks.append(matched)
            if len(chunk_mode) > len(match_mode):
                match_mode = chunk_mode

    if not chunks:
        return pd.DataFrame(), "no-match"
    return pd.concat(chunks, ignore_index=True), match_mode


def _relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_repo_root())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _build_actual_points(frame: pd.DataFrame, source_file: str, match_mode: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = (
        frame.groupby("search_date", observed=False)
        .agg(
            price=("price", "mean"),
            minPrice=("price", "min"),
            maxPrice=("price", "max"),
            sampleCount=("price", "count"),
        )
        .reset_index()
        .sort_values("search_date")
    )
    points: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        source_date = row["search_date"]
        point_dt = datetime.combine(source_date, time(12, 0, tzinfo=timezone.utc))
        day_frame = frame[frame["search_date"] == source_date]
        airlines = sorted(
            {
                str(value)
                for value in day_frame["_airline_display"].tolist()
                if isinstance(value, str) and value.strip()
            }
        )
        points.append(
            {
                "ts": _iso_z(point_dt),
                "price": round(float(row["price"]), 2),
                "minPrice": round(float(row["minPrice"]), 2),
                "maxPrice": round(float(row["maxPrice"]), 2),
                "sampleCount": int(row["sampleCount"]),
                "sourceDate": source_date.isoformat(),
                "sourceFile": source_file,
                "matchMode": match_mode,
                "airlines": airlines[:6],
                "isForecast": False,
            }
        )
    return points


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
    return round(max(min(price_delta / day_delta, 500.0), -500.0), 4)


def _ticket_to_model_flight(
    ticket: dict[str, Any],
    criteria: dict[str, Any],
    actual_points: list[dict[str, Any]],
    as_of: datetime,
) -> dict[str, Any]:
    depart_hour = criteria.get("depart_hour")
    depart_date = criteria.get("departure_date")
    depart_at = ticket.get("departAt")
    if not depart_at and depart_date:
        hour = int(depart_hour or 12)
        depart_at = datetime.combine(
            depart_date,
            time(hour % 24, 0, tzinfo=timezone.utc),
        ).isoformat()

    return {
        "uid": criteria.get("flight_id") or ticket.get("id"),
        "id": ticket.get("id"),
        "origin": criteria.get("origin"),
        "destination": criteria.get("destination"),
        "airline": ticket.get("airline") or "Unknown",
        "departAt": depart_at,
        "asOf": _iso_z(as_of),
        "currency": criteria.get("currency"),
        "stops": criteria.get("stops") or 0,
        "total_duration_minutes": criteria.get("duration_minutes") or 0,
        "recent_price_trend_per_day": recent_price_trend_per_day_from_points(actual_points),
        "segments": [
            {
                "airline": ticket.get("airline") or "Unknown",
                "duration": criteria.get("duration_minutes") or 0,
                "travel_class": ticket.get("travelClass"),
                "departure_airport": {
                    "id": criteria.get("origin"),
                    "time": depart_at,
                },
                "arrival_airport": {
                    "id": criteria.get("destination"),
                    "time": None,
                },
            }
        ],
    }


def _model_search_params(criteria: dict[str, Any]) -> dict[str, Any]:
    params = dict(criteria.get("search_params") or {})
    if criteria.get("origin"):
        params["departure_id"] = criteria["origin"]
    if criteria.get("destination"):
        params["arrival_id"] = criteria["destination"]
    if criteria.get("departure_date"):
        params["outbound_date"] = criteria["departure_date"].isoformat()
    if criteria.get("travel_class"):
        params["travel_class"] = criteria["travel_class"]
    params["currency"] = criteria.get("currency") or params.get("currency") or "USD"
    params["recent_price_trend_per_day"] = criteria.get("recent_price_trend_per_day", 0.0)
    return params


def _linear_fallback_forecast(
    actual_points: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    if len(actual_points) < 2:
        return [], None
    latest_dt = _parse_iso_datetime(actual_points[-1].get("ts"))
    first_dt = _parse_iso_datetime(actual_points[0].get("ts"))
    if latest_dt is None or first_dt is None:
        return [], None

    departure_date = criteria.get("departure_date")
    if departure_date:
        steps = min(max((departure_date - latest_dt.date()).days, 0), 7)
        if steps <= 0:
            return [], None
    else:
        steps = 7
    xs = []
    ys = []
    for point in actual_points:
        point_dt = _parse_iso_datetime(point.get("ts"))
        if point_dt is None:
            continue
        xs.append((point_dt - first_dt).total_seconds() / 86400)
        ys.append(float(point["price"]))
    if len(xs) < 2:
        return [], None

    x_mean = fmean(xs)
    y_mean = fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = 0.0 if denominator == 0 else sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    uncertainty = sqrt(sum(value**2 for value in residuals) / len(residuals)) if residuals else max(y_mean * 0.05, 5.0)

    forecast = []
    for day_idx in range(1, steps + 1):
        point_dt = latest_dt + timedelta(days=day_idx)
        x_value = (point_dt - first_dt).total_seconds() / 86400
        predicted = max(intercept + slope * x_value, 1.0)
        forecast.append(
            {
                "ts": _iso_z(point_dt),
                "price": round(predicted, 2),
                "lower": round(max(predicted - uncertainty, 1.0), 2),
                "upper": round(predicted + uncertainty, 2),
                "isForecast": True,
            }
        )
    return forecast, {
        "source": "local-linear-trend",
        "modelName": "local-linear-trend",
        "generatedAt": _iso_z(_utc_now()),
        "horizonDays": steps,
    }


def _generate_forecast_points(
    ticket: dict[str, Any],
    actual_points: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    latest_dt = (
        _parse_iso_datetime(actual_points[-1].get("ts"))
        if actual_points
        else _parse_iso_datetime(ticket.get("createdAt"))
    )
    if latest_dt is None:
        latest_dt = _utc_now()
    if latest_dt.tzinfo is None:
        latest_dt = latest_dt.replace(tzinfo=timezone.utc)

    model_criteria = dict(criteria)
    model_criteria["recent_price_trend_per_day"] = recent_price_trend_per_day_from_points(actual_points)

    departure_date = criteria.get("departure_date")
    if departure_date:
        target_days = min(max((departure_date - latest_dt.date()).days, 0), 7)
        if target_days <= 0:
            return [], None
    else:
        target_days = 7

    points = []
    primary_prediction: Optional[dict[str, Any]] = None
    all_daily_predictions: list[dict[str, Any]] = []
    for day_idx in range(1, target_days + 1):
        point_dt = latest_dt + timedelta(days=day_idx)
        try:
            prediction = predict_flight_price(
                _ticket_to_model_flight(
                    ticket,
                    model_criteria,
                    actual_points,
                    point_dt,
                ),
                _model_search_params(model_criteria),
            )
        except Exception:
            return _linear_fallback_forecast(actual_points, criteria)

        predicted_price = _to_float(prediction.get("predicted_price"))
        if predicted_price is None:
            return _linear_fallback_forecast(actual_points, criteria)
        if primary_prediction is None:
            primary_prediction = prediction
        all_daily_predictions.append(
            {
                "day": day_idx,
                "asOf": _iso_z(point_dt),
                "predictedPrice": round(predicted_price, 2),
                "modelName": prediction.get("model_name"),
                "daysToDeparture": prediction.get("features", {}).get("days_to_departure"),
            }
        )

        point = {
            "ts": _iso_z(point_dt),
            "price": round(predicted_price, 2),
            "isForecast": True,
            "modelName": prediction.get("model_name"),
            "daysToDeparture": prediction.get("features", {}).get("days_to_departure"),
        }
        lower = _to_float(prediction.get("lower"))
        upper = _to_float(prediction.get("upper"))
        if lower is not None:
            point["lower"] = round(lower, 2)
        if upper is not None:
            point["upper"] = round(upper, 2)
        points.append(point)

    if primary_prediction is None:
        return [], None

    return points, {
        "source": "joblib",
        "modelName": primary_prediction.get("model_name"),
        "modelMae": primary_prediction.get("model_mae"),
        "modelRmse": primary_prediction.get("model_rmse"),
        "modelR2": primary_prediction.get("model_r2"),
        "generatedAt": _iso_z(_utc_now()),
        "horizonDays": target_days,
        "predictedPrice": points[-1]["price"] if points else None,
        "dailyPredictions": all_daily_predictions,
        "predictions": primary_prediction.get("predictions") or [],
    }


def estimate_ticket_price_trend_per_day(ticket: dict[str, Any]) -> float:
    history = build_local_ticket_history(ticket)
    return recent_price_trend_per_day_from_points(history.get("actual") or [])


def build_local_ticket_history(
    ticket: dict[str, Any],
    max_snapshot_files: Optional[int] = None,
) -> dict[str, Any]:
    del max_snapshot_files
    criteria = _build_ticket_criteria(ticket)
    path = _features_file()
    if not path.exists():
        return {
            "ticketId": ticket.get("id"),
            "currency": criteria["currency"],
            "actual": [],
            "forecast": [],
            "forecastMeta": None,
            "summary": {
                "filesScanned": 0,
                "matchedSnapshots": 0,
                "matchedDays": 0,
                "availableDays": [],
                "departureDate": criteria["departure_date"].isoformat()
                if criteria.get("departure_date")
                else None,
                "latestPrice": None,
                "minPrice": None,
                "maxPrice": None,
                "averagePrice": None,
                "lastCapturedAt": None,
            },
            "matching": {
                "origin": criteria.get("origin"),
                "destination": criteria.get("destination"),
                "travelClass": criteria.get("travel_class"),
                "tripType": criteria.get("trip_type"),
                "passengers": criteria.get("passengers"),
                "strategy": f"{FEATURES_FILE_NAME} was not found.",
            },
        }

    cache_key = (_history_cache_token(criteria), _file_cache_key(path))
    with _HISTORY_LOCK:
        cached = _HISTORY_CACHE.get(cache_key)
    if cached is not None:
        return deepcopy(cached)

    frame, match_mode = _read_matching_frame(path, criteria)
    actual_points = _build_actual_points(frame, _relative_path(path), match_mode)
    forecast_points, forecast_meta = _generate_forecast_points(ticket, actual_points, criteria)

    prices = [float(point["price"]) for point in actual_points]
    available_days = sorted({point["sourceDate"] for point in actual_points})
    summary = {
        "filesScanned": 1,
        "matchedSnapshots": int(frame["price"].count()) if not frame.empty else 0,
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
            "sourceFile": _relative_path(path),
            "strategy": (
                f"Reads local history only from {FEATURES_FILE_NAME}; "
                "matches route first and then tightens with available ticket features. "
                "Forecast is generated by the best available joblib model ranked by MAE."
            ),
        },
    }

    with _HISTORY_LOCK:
        if len(_HISTORY_CACHE) >= _HISTORY_CACHE_MAX_SIZE:
            oldest_key = next(iter(_HISTORY_CACHE))
            _HISTORY_CACHE.pop(oldest_key, None)
        _HISTORY_CACHE[cache_key] = deepcopy(result)
    return result
