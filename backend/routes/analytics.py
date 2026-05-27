from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter

from core import _iso_z
from ml.airline_normalization import normalize_airline_value

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
MODELS_DIR = (
    BACKEND_ROOT / "ml" / "models"
    if (BACKEND_ROOT / "ml" / "models").exists()
    else REPO_ROOT / "backend" / "ml" / "models"
)
PREDICTION_SAMPLE_ROWS = 75_000
ACTIVE_MODEL_NAME = "xgboost"
PREDICTION_COLUMNS = {
    "actual_price",
    "predicted_price",
    "absolute_error",
    "absolute_error_pct",
    "departure_date",
    "travel_class",
    "airline",
    "origin",
    "destination",
}


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return round(result, 4)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _model_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metrics_path in sorted(MODELS_DIR.glob("*/metrics.json")):
        metrics = _read_json(metrics_path)
        folder = metrics_path.parent.name
        stat = metrics_path.stat()
        rows.append(
            {
                "folder": folder,
                "modelName": str(metrics.get("model") or folder),
                "mae": _safe_float(metrics.get("mae")),
                "rmse": _safe_float(metrics.get("rmse")),
                "r2": _safe_float(metrics.get("r2")),
                "mape": _safe_float(metrics.get("mape_pct")),
                "rowsUsed": _safe_int(
                    metrics.get("rows_used_for_model")
                    or metrics.get("rows_used")
                    or metrics.get("rows_after_cleaning")
                ),
                "trainRows": _safe_int(metrics.get("train_rows")),
                "testRows": _safe_int(metrics.get("test_rows")),
                "target": str(metrics.get("target") or ""),
                "updatedAt": _iso_z(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
            }
        )
    rows.sort(key=lambda item: item["mae"] if item["mae"] is not None else float("inf"))
    return rows


def _best_model_folder() -> str | None:
    rows = _model_rows()
    return rows[0]["folder"] if rows else None


def _best_model_dir() -> Path | None:
    folder = _best_model_folder()
    return MODELS_DIR / folder if folder else None


def _active_model_row() -> dict[str, Any] | None:
    rows = _model_rows()
    active = next((row for row in rows if row["folder"] == ACTIVE_MODEL_NAME), None)
    return active or (rows[0] if rows else None)


def _active_model_dir() -> Path | None:
    row = _active_model_row()
    return MODELS_DIR / row["folder"] if row else None


@lru_cache(maxsize=4)
def _read_predictions_frame(path_text: str, mtime_ns: int, size: int) -> pd.DataFrame:
    path = Path(path_text)
    frame = pd.read_csv(
        path,
        nrows=PREDICTION_SAMPLE_ROWS,
        usecols=lambda column: column in PREDICTION_COLUMNS,
    )
    if not {"actual_price", "predicted_price"}.issubset(frame.columns):
        return pd.DataFrame()
    for column in ["actual_price", "predicted_price", "absolute_error", "absolute_error_pct"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "absolute_error" not in frame.columns and {"actual_price", "predicted_price"}.issubset(frame.columns):
        frame["absolute_error"] = (frame["actual_price"] - frame["predicted_price"]).abs()
    if "absolute_error_pct" not in frame.columns and {"actual_price", "absolute_error"}.issubset(frame.columns):
        frame["absolute_error_pct"] = np.where(
            frame["actual_price"] > 0,
            frame["absolute_error"] / frame["actual_price"] * 100.0,
            np.nan,
        )
    frame["signed_error"] = frame.get("predicted_price", 0) - frame.get("actual_price", 0)
    return frame.dropna(subset=["actual_price", "predicted_price", "absolute_error"])


def _predictions_frame() -> pd.DataFrame:
    model_dir = _active_model_dir()
    if not model_dir:
        return pd.DataFrame()
    path = model_dir / "test_predictions.csv"
    if not path.exists():
        return pd.DataFrame()
    stat = path.stat()
    return _read_predictions_frame(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _records(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_travel_class(value: Any) -> str:
    if pd.isna(value):
        return "Unknown"
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
    return text or "Unknown"


def _normalized_group_frame(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in {"travel_class", "airline"}:
        return frame
    normalized = frame.copy()
    if column == "travel_class":
        normalized[column] = normalized[column].map(_normalize_travel_class)
    if column == "airline":
        normalized[column] = normalized[column].map(normalize_airline_value)
    return normalized


def _group_errors(frame: pd.DataFrame, column: str, limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty or column not in frame.columns:
        return []
    source = _normalized_group_frame(frame, column)
    grouped = (
        source.dropna(subset=[column])
        .groupby(column, observed=False)
        .agg(
            records=("actual_price", "size"),
            avgActual=("actual_price", "mean"),
            avgPredicted=("predicted_price", "mean"),
            mae=("absolute_error", "mean"),
            mape=("absolute_error_pct", "mean"),
            bias=("signed_error", "mean"),
        )
        .reset_index()
    )
    grouped = grouped.sort_values(["mae", "records"], ascending=[False, False]).head(limit)
    return [
        {
            "label": str(row[column]),
            "records": _records(row["records"]),
            "avgActual": _safe_float(row["avgActual"]),
            "avgPredicted": _safe_float(row["avgPredicted"]),
            "mae": _safe_float(row["mae"]),
            "mape": _safe_float(row["mape"]),
            "bias": _safe_float(row["bias"]),
        }
        for _, row in grouped.iterrows()
    ]


@router.get("/api/analytics/metrics")
def metrics():
    active = _active_model_row()
    if not active:
        return {}
    return {
        "mae": active["mae"],
        "rmse": active["rmse"],
        "mape": active["mape"],
        "r2": active["r2"],
        "modelName": active["modelName"],
        "updatedAt": active["updatedAt"],
        "rowsUsed": active["rowsUsed"],
        "trainRows": active["trainRows"],
        "testRows": active["testRows"],
        "target": active["target"],
    }


@router.get("/api/analytics/actual-vs-predicted")
def actual_vs_predicted():
    frame = _predictions_frame()
    if frame.empty:
        return []

    if "departure_date" in frame.columns:
        grouped = (
            frame.groupby("departure_date", observed=False)
            .agg(actual=("actual_price", "mean"), predicted=("predicted_price", "mean"))
            .reset_index()
            .sort_values("departure_date")
            .tail(30)
        )
        return [
            {
                "ts": str(row["departure_date"]),
                "actual": _safe_float(row["actual"]),
                "predicted": _safe_float(row["predicted"]),
            }
            for _, row in grouped.iterrows()
        ]

    sample = frame.head(30).copy()
    return [
        {
            "ts": str(idx + 1),
            "actual": _safe_float(row["actual_price"]),
            "predicted": _safe_float(row["predicted_price"]),
        }
        for idx, row in sample.iterrows()
    ]


@router.get("/api/analytics/dashboard")
def dashboard():
    models = _model_rows()
    active = _active_model_row()
    frame = _predictions_frame()
    model_dir = _active_model_dir()

    feature_importance: list[dict[str, Any]] = []
    if model_dir:
        path = model_dir / "feature_importance.csv"
        if path.exists():
            importance = pd.read_csv(path).head(12)
            if {"feature", "importance"}.issubset(importance.columns):
                total = pd.to_numeric(importance["importance"], errors="coerce").sum()
                for _, row in importance.iterrows():
                    value = _safe_float(row["importance"])
                    share = _safe_float((float(row["importance"]) / total * 100.0) if total else None)
                    feature_importance.append(
                        {
                            "feature": str(row["feature"]),
                            "importance": value,
                            "share": share,
                        }
                    )

    error_by_price_bucket: list[dict[str, Any]] = []
    if not frame.empty and frame["actual_price"].nunique() > 1:
        labels = ["very low", "low", "medium", "high", "very high"]
        bucket_count = min(len(labels), int(frame["actual_price"].nunique()))
        working = frame.copy()
        working["priceBucket"] = pd.qcut(
            working["actual_price"],
            q=bucket_count,
            labels=labels[:bucket_count],
            duplicates="drop",
        )
        error_by_price_bucket = _group_errors(working, "priceBucket", limit=10)

    route_frame = frame.copy()
    if {"origin", "destination"}.issubset(route_frame.columns):
        route_frame["route"] = route_frame["origin"].astype(str) + " - " + route_frame["destination"].astype(str)
        route_counts = route_frame["route"].value_counts()
        enough = route_counts[route_counts >= 20].index
        route_frame = route_frame.loc[route_frame["route"].isin(enough)]

    recommendation_mix: list[dict[str, Any]] = []
    if not frame.empty:
        working = frame.loc[frame["predicted_price"] > 0].copy()
        working["gapPct"] = (working["actual_price"] - working["predicted_price"]) / working["predicted_price"] * 100.0
        working["recommendation"] = np.select(
            [
                working["gapPct"] <= -10,
                working["gapPct"].between(-10, 10, inclusive="both"),
                working["gapPct"] > 10,
            ],
            ["buy now", "neutral", "wait"],
            default="unknown",
        )
        grouped = (
            working.groupby("recommendation", observed=False)
            .agg(records=("actual_price", "size"), avgGapPct=("gapPct", "mean"), avgActual=("actual_price", "mean"))
            .reset_index()
            .sort_values("records", ascending=False)
        )
        recommendation_mix = [
            {
                "label": str(row["recommendation"]),
                "records": _records(row["records"]),
                "avgGapPct": _safe_float(row["avgGapPct"]),
                "avgActual": _safe_float(row["avgActual"]),
            }
            for _, row in grouped.iterrows()
        ]

    sample_size = len(frame)
    avg_actual = _safe_float(frame["actual_price"].mean()) if not frame.empty else None
    avg_predicted = _safe_float(frame["predicted_price"].mean()) if not frame.empty else None
    median_error = _safe_float(frame["absolute_error"].median()) if not frame.empty else None

    insights = []
    if active:
        insights.append(
            {
                "title": "Active forecast model",
                "value": active["modelName"],
                "body": f"MAE {active['mae']} with R2 {active['r2']}; compared against {len(models)} trained artifacts.",
            }
        )
    if models and active and models[0]["folder"] != active["folder"]:
        insights.append(
            {
                "title": "Best benchmark",
                "value": models[0]["modelName"],
                "body": f"This artifact has MAE {models[0]['mae']}; keep it visible as a candidate for a future deployment.",
            }
        )
    if feature_importance:
        top = feature_importance[0]
        insights.append(
            {
                "title": "Main driver",
                "value": top["feature"],
                "body": f"This feature contributes about {top['share']}% of the visible top-feature importance.",
            }
        )
    if error_by_price_bucket:
        risky = error_by_price_bucket[0]
        insights.append(
            {
                "title": "Hardest price segment",
                "value": risky["label"],
                "body": f"Average error is {risky['mae']}; show recommendations with more caution here.",
            }
        )

    return {
        "sampleSize": sample_size,
        "modelRanking": models,
        "featureImportance": feature_importance,
        "errorByPriceBucket": error_by_price_bucket,
        "errorByTravelClass": _group_errors(frame, "travel_class", limit=8),
        "errorByAirline": _group_errors(frame, "airline", limit=10),
        "errorByRoute": _group_errors(route_frame, "route", limit=10),
        "recommendationMix": recommendation_mix,
        "summary": {
            "avgActual": avg_actual,
            "avgPredicted": avg_predicted,
            "medianError": median_error,
            "rowsAnalyzed": sample_size,
            "modelsFound": len(models),
        },
        "insights": insights,
    }
