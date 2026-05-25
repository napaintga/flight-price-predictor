"""Serve the best trained flight price model for API predictions."""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.airline_normalization import normalize_airline_value

MODEL_NAME = "xgboost"

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "backend" / "ml" / "models"
MODEL_DIR = MODELS_DIR / MODEL_NAME
MODEL_PATH = MODEL_DIR / f"{MODEL_NAME}_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
AIRPORTS_PATH = REPO_ROOT / "etl" / "airflow" / "world-airports.csv"

FEATURE_COLUMNS = [
    "days_to_departure",
    "stops",
    "duration_minutes",
    "distance_km",
    "depart_hour",
    "recent_price_trend_per_day",
    "travel_class",
    "airline",
    "origin",
    "destination",
    "arrival_time",
    "search_month",
    "depart_dow",
    "depart_month",
]

NUMERIC_COLUMNS = [
    "days_to_departure",
    "stops",
    "duration_minutes",
    "distance_km",
    "depart_hour",
    "recent_price_trend_per_day",
]

TRAVEL_CLASS_LABELS = {
    1: "Economy Class",
    2: "Premium Economy",
    3: "Business Class",
    4: "First Class",
}


def _model_dir(model_name: str) -> Path:
    return MODELS_DIR / model_name


def _model_path(model_name: str) -> Path:
    model_dir = _model_dir(model_name)
    exact = model_dir / f"{model_name}_model.joblib"
    if exact.exists():
        return exact
    candidates = sorted(model_dir.glob("*_model.joblib"))
    if candidates:
        return candidates[0]
    return exact


@lru_cache(maxsize=1)
def _ranked_prediction_model_names() -> tuple[str, ...]:
    rows: list[tuple[float, str]] = []
    for metrics_path in sorted(MODELS_DIR.glob("*/metrics.json")):
        model_name = metrics_path.parent.name
        if not _model_path(model_name).exists():
            continue
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            mae = float(metrics.get("mae"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if np.isfinite(mae):
            rows.append((mae, model_name))
    rows.sort(key=lambda item: item[0])
    names = [model_name for _, model_name in rows[:2]]
    if MODEL_NAME not in names and _model_path(MODEL_NAME).exists() and len(names) < 2:
        names.append(MODEL_NAME)
    return tuple(names or [MODEL_NAME])


@lru_cache(maxsize=4)
def _load_model(model_name: str = MODEL_NAME) -> Any:
    path = _model_path(model_name)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)


@lru_cache(maxsize=4)
def _load_model_metrics(model_name: str = MODEL_NAME) -> dict[str, Any]:
    path = _model_dir(model_name) / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_airports() -> dict[str, tuple[float, float]]:
    airports: dict[str, tuple[float, float]] = {}
    if not AIRPORTS_PATH.exists():
        return airports

    with AIRPORTS_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = (row.get("iata_code") or "").strip().upper()
            if not code:
                continue
            try:
                lat = float(row.get("latitude_deg") or "")
                lon = float(row.get("longitude_deg") or "")
            except ValueError:
                continue
            airports[code] = (lat, lon)
    return airports


def _haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1 = first
    lat2, lon2 = second
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_km * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _distance_km(origin: str | None, destination: str | None) -> float:
    if not origin or not destination:
        return float("nan")
    airports = _load_airports()
    first = airports.get(origin.upper())
    second = airports.get(destination.upper())
    if not first or not second:
        return float("nan")
    return _haversine_km(first, second)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass

    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M"):
        try:
            parsed = datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return None


def _parse_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.date()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_hour(value: Any) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value) % 24

    parsed = _parse_datetime(value)
    if parsed:
        return float(parsed.hour)

    text = str(value).strip()
    if not text:
        return float("nan")

    match = re.search(r"\b(\d{1,2})(?::\d{2})?\s*(AM|PM)?\b", text, re.IGNORECASE)
    if not match:
        return float("nan")

    hour = int(match.group(1))
    suffix = (match.group(2) or "").upper()
    if suffix == "PM" and hour < 12:
        hour += 12
    if suffix == "AM" and hour == 12:
        hour = 0
    return float(hour % 24)


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _time_period_from_hour(hour: float) -> str:
    if not np.isfinite(hour):
        return "Unknown"
    value = int(hour) % 24
    if 5 <= value < 12:
        return "Morning"
    if 12 <= value < 18:
        return "Afternoon"
    if 18 <= value < 22:
        return "Evening"
    return "Night"


def _first_segment(flight: dict[str, Any]) -> dict[str, Any]:
    segments = flight.get("segments") or []
    return segments[0] if segments else {}


def _last_segment(flight: dict[str, Any]) -> dict[str, Any]:
    segments = flight.get("segments") or []
    return segments[-1] if segments else {}


def _segment_departure_time(segment: dict[str, Any]) -> Any:
    return (segment.get("departure_airport") or {}).get("time")


def _segment_arrival_time(segment: dict[str, Any]) -> Any:
    return (segment.get("arrival_airport") or {}).get("time")


def _first_iata(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    return text.split(",")[0].strip() or None


def _travel_class_from_params(value: Any) -> str:
    try:
        return TRAVEL_CLASS_LABELS.get(int(value), "Economy")
    except (TypeError, ValueError):
        return "Economy Class"


def _normalize_travel_class(value: Any) -> str:
    if pd.isna(value):
        return "Economy Class"
    text = str(value).strip()
    if not text:
        return "Economy Class"
    normalized = text.lower()
    if normalized in {"economy", "economy class"}:
        return "Economy Class"
    if normalized in {"premium economy", "premium economy class"}:
        return "Premium Economy"
    if normalized in {"business", "business class"}:
        return "Business Class"
    if normalized in {"first", "first class"}:
        return "First Class"
    return text


def build_model_features(
    flight: dict[str, Any],
    search_params: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    first = _first_segment(flight)
    last = _last_segment(flight)

    origin = (
        flight.get("origin")
        or (first.get("departure_airport") or {}).get("id")
        or _first_iata(search_params.get("departure_id"))
        or "Unknown"
    )
    destination = (
        flight.get("destination")
        or (last.get("arrival_airport") or {}).get("id")
        or _first_iata(search_params.get("arrival_id"))
        or "Unknown"
    )

    departure_date = (
        _parse_date(search_params.get("outbound_date"))
        or _parse_date(flight.get("departAt"))
        or _parse_date(_segment_departure_time(first))
    )
    as_of = _parse_datetime(flight.get("asOf")) or datetime.now(timezone.utc)
    search_date = as_of.date()
    days_to_departure = (
        max((departure_date - search_date).days, 0) if departure_date else 0
    )

    depart_hour = _parse_hour(_segment_departure_time(first) or flight.get("departAt"))
    arrival_hour = _parse_hour(_segment_arrival_time(last) or flight.get("arrivalAt"))
    arrival_time = _time_period_from_hour(arrival_hour)

    duration_minutes = flight.get("total_duration_minutes")
    if duration_minutes is None:
        duration_minutes = sum(
            int(segment.get("duration") or 0)
            for segment in (flight.get("segments") or [])
        )

    travel_class = (
        first.get("travel_class")
        or flight.get("travel_class")
        or _travel_class_from_params(search_params.get("travel_class"))
    )

    row = {
        "days_to_departure": float(days_to_departure),
        "stops": float(flight.get("stops") or 0),
        "duration_minutes": float(duration_minutes or 0),
        "distance_km": float(_distance_km(str(origin), str(destination))),
        "depart_hour": float(depart_hour),
        "recent_price_trend_per_day": _parse_float(
            flight.get("recent_price_trend_per_day")
            or search_params.get("recent_price_trend_per_day"),
            0.0,
        ),
        "travel_class": _normalize_travel_class(travel_class),
        "airline": normalize_airline_value(flight.get("airline") or first.get("airline") or "Unknown"),
        "origin": str(origin).strip().upper() or "Unknown",
        "destination": str(destination).strip().upper() or "Unknown",
        "arrival_time": arrival_time,
        "search_month": str(search_date.month),
        "depart_dow": str(departure_date.weekday() if departure_date else search_date.weekday()),
        "depart_month": str(departure_date.month if departure_date else search_date.month),
    }

    frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in set(FEATURE_COLUMNS).difference(NUMERIC_COLUMNS):
        frame[column] = frame[column].astype("string").fillna("Unknown")

    return frame, row


def _predict_hierarchical_median(model: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    base = frame.copy()
    base["_row_position"] = np.arange(len(base))
    predicted = np.full(len(base), np.nan, dtype=float)

    for lookup in model.get("hierarchies", []):
        keys = lookup.get("keys") or []
        table = lookup.get("table")
        if not keys or table is None or table.empty:
            continue

        merged = base[["_row_position"] + keys].merge(
            table[keys + ["prediction_log"]],
            on=keys,
            how="left",
        )
        has_prediction = merged["prediction_log"].notna().to_numpy()
        positions = merged["_row_position"].to_numpy()
        missing = np.isnan(predicted[positions])
        fill_mask = has_prediction & missing
        if np.any(fill_mask):
            predicted[positions[fill_mask]] = merged.loc[
                fill_mask, "prediction_log"
            ].to_numpy()

    predicted[np.isnan(predicted)] = float(model["global_prediction_log"])
    return predicted


def _predict_log_price(model_name: str, frame: pd.DataFrame) -> float:
    model = _load_model(model_name)
    if isinstance(model, dict) and model.get("type") == "hierarchical_median_log_price":
        return float(_predict_hierarchical_median(model, frame)[0])
    return float(model.predict(frame)[0])


def _prediction_detail(
    *,
    model_name: str,
    frame: pd.DataFrame,
    currency: str,
) -> dict[str, Any]:
    metrics = _load_model_metrics(model_name)
    predicted_log = _predict_log_price(model_name, frame)
    predicted_price = max(float(np.expm1(predicted_log)), 0.0)
    mae = metrics.get("mae")
    band = float(mae) if mae is not None else max(predicted_price * 0.15, 25.0)
    return {
        "modelName": model_name,
        "model": model_name,
        "predictedPrice": round(predicted_price, 2),
        "lower": round(max(predicted_price - band, 1.0), 2),
        "upper": round(predicted_price + band, 2),
        "currency": currency,
        "modelMae": float(mae) if mae is not None else None,
        "modelRmse": float(metrics["rmse"]) if metrics.get("rmse") is not None else None,
        "modelR2": float(metrics["r2"]) if metrics.get("r2") is not None else None,
    }


def predict_flight_price(
    flight: dict[str, Any],
    search_params: dict[str, Any],
) -> dict[str, Any]:
    frame, features = build_model_features(flight, search_params)
    currency = flight.get("currency") or search_params.get("currency") or "USD"
    predictions = []
    for model_name in _ranked_prediction_model_names():
        try:
            predictions.append(
                _prediction_detail(model_name=model_name, frame=frame, currency=currency)
            )
        except Exception:
            continue
    if not predictions:
        predictions.append(
            _prediction_detail(model_name=MODEL_NAME, frame=frame, currency=currency)
        )
    primary = predictions[0]

    return {
        "predicted_price": primary["predictedPrice"],
        "lower": primary["lower"],
        "upper": primary["upper"],
        "currency": primary["currency"],
        "model_name": primary["modelName"],
        "model_mae": primary["modelMae"],
        "model_rmse": primary["modelRmse"],
        "model_r2": primary["modelR2"],
        "predictions": predictions,
        "features": features,
    }
