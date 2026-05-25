"""Shared helpers for the forecasting notebooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from airline_normalization import normalize_airline_value
from forecast_features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    REMOVED_FEATURES,
    TARGET_COLUMN,
)

PREDICTION_ID_COLUMNS = [
    "flight_id",
    "departure_date",
    "origin",
    "destination",
    "airline",
    "travel_class",
]

TRAINING_ORIGIN_COUNTRIES = ("GB", "PL")
TRAINING_DESTINATION_COUNTRIES = ("IT", "FR")
TRAINING_TRIP_TYPES = ("one-way",)
TRAINING_TRAVEL_CLASSES = ("Economy Class", "Business Class")
NORMALIZATION_VERSION = "travel-class-country-trip-airline-v1"

AIRPORT_COUNTRY_BY_IATA = {
    "LHR": "GB",
    "LGW": "GB",
    "MAN": "GB",
    "KRK": "PL",
    "WMI": "PL",
    "WAW": "PL",
    "RZE": "PL",
    "KTW": "PL",
    "WRO": "PL",
    "FCO": "IT",
    "MXP": "IT",
    "VCE": "IT",
    "CDG": "FR",
    "ORY": "FR",
    "MRS": "FR",
    "NCE": "FR",
}

FILTER_COLUMNS = ["trip_type"]
READ_COLUMNS = list(dict.fromkeys(FEATURE_COLUMNS + [TARGET_COLUMN] + PREDICTION_ID_COLUMNS + FILTER_COLUMNS))
DERIVED_FEATURE_COLUMNS = {"recent_price_trend_per_day"}
TREND_GROUP_COLUMNS = [
    "origin",
    "destination",
    "departure_date",
    "airline",
    "travel_class",
    "trip_type",
    "stops",
    "duration_minutes",
    "depart_hour",
]


def normalize_travel_class_value(value: Any) -> str:
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


def normalize_trip_type_value(value: Any) -> str:
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    normalized = text.lower().replace("_", "-").replace(" ", "-")
    if normalized in {"oneway", "one-way", "2"}:
        return "one-way"
    if normalized in {"roundtrip", "round-trip", "round", "1"}:
        return "round-trip"
    return normalized or "Unknown"


def airport_country(value: Any) -> str:
    if pd.isna(value):
        return ""
    code = str(value).strip().upper()
    return AIRPORT_COUNTRY_BY_IATA.get(code, "")


def read_forecast_dataset(input_path: str | Path, limit_rows: int | None = None) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    return pd.read_csv(
        path,
        low_memory=False,
        nrows=limit_rows,
        usecols=lambda column: str(column).strip() in READ_COLUMNS,
    )


def normalize_forecast_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df.columns = [str(column).strip() for column in df.columns]
    required_features = [column for column in FEATURE_COLUMNS if column not in DERIVED_FEATURE_COLUMNS]
    missing = [column for column in required_features + [TARGET_COLUMN] if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in NUMERIC_FEATURES + [TARGET_COLUMN]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in CATEGORICAL_FEATURES:
        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
            .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "null": pd.NA})
            .fillna("Unknown")
        )

    if "travel_class" in df.columns:
        df["travel_class"] = df["travel_class"].map(normalize_travel_class_value)
    if "trip_type" in df.columns:
        df["trip_type"] = df["trip_type"].map(normalize_trip_type_value)
    if "airline" in df.columns:
        df["airline"] = df["airline"].map(normalize_airline_value)

    return df


def add_recent_price_trend_feature(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    feature = "recent_price_trend_per_day"

    if {TARGET_COLUMN, "days_to_departure"}.difference(df.columns):
        df[feature] = 0.0
        return df

    group_columns = [column for column in TREND_GROUP_COLUMNS if column in df.columns]
    if not group_columns:
        df[feature] = 0.0
        return df

    work = df[group_columns + [TARGET_COLUMN, "days_to_departure"]].copy()
    work["_source_index"] = df.index
    work[TARGET_COLUMN] = pd.to_numeric(work[TARGET_COLUMN], errors="coerce")
    work["days_to_departure"] = pd.to_numeric(work["days_to_departure"], errors="coerce")
    work = work.sort_values(group_columns + ["days_to_departure"], ascending=[True] * len(group_columns) + [False])

    grouped = work.groupby(group_columns, dropna=False, sort=False)
    previous_price = grouped[TARGET_COLUMN].shift(1)
    earlier_price = grouped[TARGET_COLUMN].shift(2)
    previous_days = grouped["days_to_departure"].shift(1)
    earlier_days = grouped["days_to_departure"].shift(2)
    day_delta = earlier_days - previous_days
    trend = (previous_price - earlier_price) / day_delta.replace(0, np.nan)
    trend = trend.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-500.0, 500.0)

    aligned = pd.Series(trend.to_numpy(), index=work["_source_index"])
    df[feature] = aligned.reindex(df.index).fillna(0.0).astype(float)
    return df


def filter_training_scope(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()

    origin_country = df["origin"].map(airport_country) if "origin" in df.columns else pd.Series("", index=df.index)
    destination_country = (
        df["destination"].map(airport_country) if "destination" in df.columns else pd.Series("", index=df.index)
    )

    mask = (
        origin_country.isin(TRAINING_ORIGIN_COUNTRIES)
        & destination_country.isin(TRAINING_DESTINATION_COUNTRIES)
    )

    if "trip_type" in df.columns:
        mask &= df["trip_type"].map(normalize_trip_type_value).isin(TRAINING_TRIP_TYPES)
    if "travel_class" in df.columns:
        mask &= df["travel_class"].map(normalize_travel_class_value).isin(TRAINING_TRAVEL_CLASSES)

    return df.loc[mask].copy()


def existing_output_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in PREDICTION_ID_COLUMNS if column in frame.columns]


def clean_forecast_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = normalize_forecast_frame(frame)
    df = filter_training_scope(df)
    df = add_recent_price_trend_feature(df)
    valid_mask = (
        df[TARGET_COLUMN].gt(0)
        & df["days_to_departure"].ge(0)
        & df["distance_km"].gt(0)
        & df["duration_minutes"].gt(0)
        & df["stops"].ge(0)
    )
    keep_columns = list(dict.fromkeys(FEATURE_COLUMNS + [TARGET_COLUMN] + existing_output_columns(df)))
    return df.loc[valid_mask, keep_columns].dropna(subset=[TARGET_COLUMN])


def sample_rows(frame: pd.DataFrame, sample_size: int, random_state: int = 42) -> pd.DataFrame:
    if sample_size <= 0 or len(frame) <= sample_size:
        return frame
    return frame.sample(sample_size, random_state=random_state)


def build_preprocessor() -> ColumnTransformer:
    try:
        encoder = OneHotEncoder(
            handle_unknown="infrequent_if_exist",
            min_frequency=25,
            sparse_output=True,
        )
    except TypeError:
        encoder = OneHotEncoder(handle_unknown="ignore")

    return ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", encoder),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def split_features_target(
    frame: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    x = frame[FEATURE_COLUMNS]
    y = np.log1p(frame[TARGET_COLUMN].astype(float))
    return train_test_split(x, y, test_size=test_size, random_state=random_state)


def evaluate_log_predictions(actual_log: pd.Series, predicted_log: np.ndarray) -> dict[str, float]:
    actual = np.expm1(actual_log)
    predicted = np.maximum(np.expm1(predicted_log), 0)
    non_zero = actual.replace(0, np.nan)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "mape_pct": float((np.abs(actual - predicted) / non_zero).mean() * 100.0),
    }


def prediction_table(source: pd.DataFrame, actual_log: pd.Series, predicted_log: np.ndarray) -> pd.DataFrame:
    result = source[existing_output_columns(source)].copy()
    actual = np.expm1(actual_log).to_numpy()
    predicted = np.maximum(np.expm1(predicted_log), 0)
    result["actual_price"] = np.round(actual, 2)
    result["predicted_price"] = np.round(predicted, 2)
    result["absolute_error"] = np.round(np.abs(actual - predicted), 2)
    result["absolute_error_pct"] = np.round(
        np.where(actual > 0, np.abs(actual - predicted) / actual * 100.0, np.nan),
        2,
    )
    return result


def aggregate_encoded_feature_values(values: np.ndarray, feature_names: np.ndarray) -> pd.DataFrame:
    detailed = pd.DataFrame({"encoded_feature": feature_names, "value": values})
    cleaned = detailed["encoded_feature"].astype(str).str.replace(
        r"^(numeric|categorical)__",
        "",
        regex=True,
    )
    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLUMNS:
        mask = cleaned.eq(feature) | cleaned.str.startswith(feature + "_")
        rows.append({"feature": feature, "value": float(detailed.loc[mask, "value"].sum())})
    return pd.DataFrame(rows).sort_values("value", key=lambda s: s.abs(), ascending=False)


def feature_importance_from_pipeline(pipeline: Pipeline) -> pd.DataFrame:
    estimator = pipeline.named_steps["model"]
    preprocessor = pipeline.named_steps["preprocess"]
    feature_names = preprocessor.get_feature_names_out()

    if hasattr(estimator, "feature_importances_"):
        result = aggregate_encoded_feature_values(estimator.feature_importances_, feature_names)
        return result.rename(columns={"value": "importance"})

    if hasattr(estimator, "coef_"):
        coef = np.ravel(estimator.coef_)
        result = aggregate_encoded_feature_values(np.abs(coef), feature_names)
        return result.rename(columns={"value": "abs_coefficient"})

    return pd.DataFrame({"feature": FEATURE_COLUMNS})


def save_forecast_outputs(
    output_dir: str | Path,
    model_name: str,
    model: Any,
    metrics: dict[str, Any],
    predictions: pd.DataFrame,
    feature_importance: pd.DataFrame | None = None,
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path / f"{model_name}_model.joblib")
    (path / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    predictions.to_csv(path / "test_predictions.csv", index=False, encoding="utf-8")
    if feature_importance is not None and not feature_importance.empty:
        feature_importance.to_csv(path / "feature_importance.csv", index=False, encoding="utf-8")


def train_sklearn_forecaster(
    model_name: str,
    estimator: Any,
    input_path: str | Path,
    output_dir: str | Path,
    sample_size: int = 0,
    limit_rows: int | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    raw = read_forecast_dataset(input_path, limit_rows=limit_rows)
    cleaned = clean_forecast_frame(raw)
    data = sample_rows(cleaned, sample_size=sample_size, random_state=random_state)
    x_train, x_test, y_train, y_test = split_features_target(data, test_size, random_state)

    model = Pipeline(steps=[("preprocess", build_preprocessor()), ("model", estimator)])
    model.fit(x_train, y_train)
    predicted_log = model.predict(x_test)

    metrics = evaluate_log_predictions(y_test, predicted_log)
    metrics.update(
        {
            "model": model_name,
            "target": "log1p(price)",
            "rows_in_file_or_read": int(len(raw)),
            "rows_after_cleaning": int(len(cleaned)),
            "rows_used_for_model": int(len(data)),
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
            "refit_on_full_data": True,
            "final_fit_rows": int(len(data)),
            "features": FEATURE_COLUMNS,
            "removed_columns": REMOVED_FEATURES,
            "training_scope": {
                "origin_countries": TRAINING_ORIGIN_COUNTRIES,
                "destination_countries": TRAINING_DESTINATION_COUNTRIES,
                "trip_types": TRAINING_TRIP_TYPES,
                "travel_classes": TRAINING_TRAVEL_CLASSES,
            },
            "normalization": {
                "version": NORMALIZATION_VERSION,
                "airline": "canonical aliases, deduplicated and sorted multi-carrier labels",
                "travel_class": "canonical display labels",
                "trip_type": "canonical one-way/round-trip labels",
                "recent_price_trend_per_day": "causal slope from previous local price observations",
            },
        }
    )

    predictions = prediction_table(data.loc[x_test.index], y_test, predicted_log)
    # Save a final artifact that has been trained on every row used for this run.
    model.fit(data[FEATURE_COLUMNS], np.log1p(data[TARGET_COLUMN].astype(float)))
    importance = feature_importance_from_pipeline(model)
    save_forecast_outputs(output_dir, model_name, model, metrics, predictions, importance)
    return {
        "metrics": metrics,
        "feature_importance": importance,
        "predictions": predictions,
        "model": model,
    }
