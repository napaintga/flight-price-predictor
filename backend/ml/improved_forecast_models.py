"""Improved training routines for the weaker forecasting models."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from forecast_features import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES, REMOVED_FEATURES, TARGET_COLUMN
from forecast_model_utils import (
    NORMALIZATION_VERSION,
    TRAINING_DESTINATION_COUNTRIES,
    TRAINING_ORIGIN_COUNTRIES,
    TRAINING_TRAVEL_CLASSES,
    TRAINING_TRIP_TYPES,
    clean_forecast_frame,
    evaluate_log_predictions,
    prediction_table,
    read_forecast_dataset,
    sample_rows,
    save_forecast_outputs,
)

MEAN_BASELINE_HIERARCHIES = [
    ["travel_class", "stops", "airline", "origin", "destination"],
    ["travel_class", "stops", "airline"],
    ["travel_class", "stops"],
    ["travel_class"],
]

ROUTE_BASELINE_HIERARCHIES = [
    ["origin", "destination", "travel_class", "stops", "airline", "arrival_time", "depart_month"],
    ["origin", "destination", "travel_class", "stops", "airline"],
    ["origin", "destination", "travel_class", "stops"],
    ["origin", "destination", "travel_class"],
    ["origin", "destination"],
]


def training_scope_metrics() -> dict[str, Any]:
    return {
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
        }
    }


def parse_float_list(value: str) -> list[float]:
    result = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not result:
        raise argparse.ArgumentTypeError("Expected at least one float value.")
    return result


def load_train_test_data(
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = read_forecast_dataset(args.input, limit_rows=args.limit_rows)
    cleaned = clean_forecast_frame(raw)
    data = sample_rows(cleaned, sample_size=args.sample_size, random_state=args.random_state)
    train_frame, test_frame = train_test_split(
        data,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    return raw, cleaned, data.copy(), train_frame.copy(), test_frame.copy()


def fit_hierarchical_median_model(
    train_frame: pd.DataFrame,
    hierarchies: list[list[str]],
    min_group_size: int,
) -> dict[str, Any]:
    work = train_frame.copy()
    work["_target_log"] = np.log1p(work[TARGET_COLUMN].astype(float))
    lookups: list[dict[str, Any]] = []

    for keys in hierarchies:
        grouped = (
            work.groupby(keys, dropna=False)["_target_log"]
            .agg(["median", "count"])
            .reset_index()
        )
        grouped = grouped.loc[grouped["count"].ge(min_group_size)].copy()
        grouped = grouped.rename(columns={"median": "prediction_log"})
        lookups.append(
            {
                "keys": keys,
                "table": grouped[keys + ["prediction_log", "count"]],
            }
        )

    return {
        "type": "hierarchical_median_log_price",
        "global_prediction_log": float(work["_target_log"].median()),
        "min_group_size": min_group_size,
        "hierarchies": lookups,
    }


def predict_hierarchical_median(model: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    base = frame.copy()
    base["_row_position"] = np.arange(len(base))
    predicted = np.full(len(base), np.nan, dtype=float)

    for lookup in model["hierarchies"]:
        keys = lookup["keys"]
        table = lookup["table"]
        if table.empty:
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
            predicted[positions[fill_mask]] = merged.loc[fill_mask, "prediction_log"].to_numpy()

    predicted[np.isnan(predicted)] = model["global_prediction_log"]
    return predicted


def _baseline_metrics(
    *,
    raw: pd.DataFrame,
    cleaned: pd.DataFrame,
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    model_name: str,
    predicted_log: np.ndarray,
    fit_seconds: float,
    extra: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    y_test_log = np.log1p(test_frame[TARGET_COLUMN].astype(float))
    metrics = evaluate_log_predictions(y_test_log, predicted_log)
    metrics.update(
        {
            "model": model_name,
            "target": "log1p(price)",
            "rows_in_file_or_read": int(len(raw)),
            "rows_after_cleaning": int(len(cleaned)),
            "rows_used_for_model": int(len(train_frame) + len(test_frame)),
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "fit_seconds": round(fit_seconds, 3),
            "features": FEATURE_COLUMNS,
            "removed_columns": REMOVED_FEATURES,
            **training_scope_metrics(),
            **extra,
        }
    )
    return metrics, prediction_table(test_frame, y_test_log, predicted_log)


def train_hierarchical_mean_baseline(args: argparse.Namespace) -> dict[str, Any]:
    raw, cleaned, data, train_frame, test_frame = load_train_test_data(args)
    started = perf_counter()
    evaluation_model = fit_hierarchical_median_model(
        train_frame,
        hierarchies=MEAN_BASELINE_HIERARCHIES,
        min_group_size=args.min_group_size,
    )
    predicted_log = predict_hierarchical_median(evaluation_model, test_frame)
    model = fit_hierarchical_median_model(
        data,
        hierarchies=MEAN_BASELINE_HIERARCHIES,
        min_group_size=args.min_group_size,
    )
    metrics, predictions = _baseline_metrics(
        raw=raw,
        cleaned=cleaned,
        train_frame=train_frame,
        test_frame=test_frame,
        model_name="mean_baseline",
        predicted_log=predicted_log,
        fit_seconds=perf_counter() - started,
        extra={
            "improved_model": "mean_baseline_hierarchical",
            "strategy": "hierarchical median fallback",
            "min_group_size": args.min_group_size,
            "hierarchy_count": len(MEAN_BASELINE_HIERARCHIES),
            "refit_on_full_data": True,
            "final_fit_rows": int(len(data)),
        },
    )
    save_forecast_outputs(args.output, "mean_baseline", model, metrics, predictions, pd.DataFrame())
    return {"metrics": metrics, "predictions": predictions, "model": model}


def train_hierarchical_route_mean_baseline(args: argparse.Namespace) -> dict[str, Any]:
    raw, cleaned, data, train_frame, test_frame = load_train_test_data(args)
    started = perf_counter()
    evaluation_model = fit_hierarchical_median_model(
        train_frame,
        hierarchies=ROUTE_BASELINE_HIERARCHIES,
        min_group_size=args.min_group_size,
    )
    predicted_log = predict_hierarchical_median(evaluation_model, test_frame)
    model = fit_hierarchical_median_model(
        data,
        hierarchies=ROUTE_BASELINE_HIERARCHIES,
        min_group_size=args.min_group_size,
    )
    metrics, predictions = _baseline_metrics(
        raw=raw,
        cleaned=cleaned,
        train_frame=train_frame,
        test_frame=test_frame,
        model_name="route_mean_baseline",
        predicted_log=predicted_log,
        fit_seconds=perf_counter() - started,
        extra={
            "improved_model": "route_mean_baseline_hierarchical",
            "strategy": "route-aware hierarchical median fallback",
            "min_group_size": args.min_group_size,
            "hierarchy_count": len(ROUTE_BASELINE_HIERARCHIES),
            "refit_on_full_data": True,
            "final_fit_rows": int(len(data)),
        },
    )
    save_forecast_outputs(args.output, "route_mean_baseline", model, metrics, predictions, pd.DataFrame())
    return {"metrics": metrics, "predictions": predictions, "model": model}


def make_scaled_elasticnet_preprocessor(min_frequency: int) -> ColumnTransformer:
    try:
        encoder = OneHotEncoder(
            handle_unknown="infrequent_if_exist",
            min_frequency=min_frequency,
            sparse_output=True,
        )
    except TypeError:
        encoder = OneHotEncoder(handle_unknown="ignore")

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", encoder),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def fit_elasticnet_sgd(
    *,
    train_frame: pd.DataFrame,
    alpha: float,
    l1_ratio: float,
    min_frequency: int,
    random_state: int,
    max_iter: int,
) -> Pipeline:
    model = Pipeline(
        steps=[
            ("preprocess", make_scaled_elasticnet_preprocessor(min_frequency)),
            (
                "model",
                SGDRegressor(
                    loss="squared_error",
                    penalty="elasticnet",
                    alpha=alpha,
                    l1_ratio=l1_ratio,
                    max_iter=max_iter,
                    tol=1e-3,
                    learning_rate="adaptive",
                    eta0=0.001,
                    early_stopping=True,
                    validation_fraction=0.1,
                    n_iter_no_change=10,
                    average=True,
                    random_state=random_state,
                ),
            ),
        ]
    )
    model.fit(train_frame[FEATURE_COLUMNS], np.log1p(train_frame[TARGET_COLUMN].astype(float)))
    return model


def safe_evaluate_log_predictions(
    actual_log: pd.Series,
    predicted_log: np.ndarray,
) -> dict[str, float]:
    predicted = np.asarray(predicted_log, dtype=float)
    if not np.all(np.isfinite(predicted)):
        return {"mae": float("inf"), "rmse": float("inf"), "r2": float("-inf"), "mape_pct": float("inf")}
    if np.nanmax(np.abs(predicted)) > 30:
        return {"mae": float("inf"), "rmse": float("inf"), "r2": float("-inf"), "mape_pct": float("inf")}
    return evaluate_log_predictions(actual_log, predicted)


def train_scaled_tuned_elasticnet(args: argparse.Namespace) -> dict[str, Any]:
    raw, cleaned, data, train_frame, test_frame = load_train_test_data(args)
    inner_train, validation = train_test_split(
        train_frame,
        test_size=args.validation_size,
        random_state=args.random_state,
    )
    validation_log = np.log1p(validation[TARGET_COLUMN].astype(float))
    tuning_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    started = perf_counter()

    for alpha, l1_ratio in itertools.product(args.elasticnet_alphas, args.elasticnet_l1_ratios):
        candidate_started = perf_counter()
        model = fit_elasticnet_sgd(
            train_frame=inner_train,
            alpha=alpha,
            l1_ratio=l1_ratio,
            min_frequency=args.categorical_min_frequency,
            random_state=args.random_state,
            max_iter=args.elasticnet_max_iter,
        )
        predicted_log = model.predict(validation[FEATURE_COLUMNS])
        candidate_metrics = safe_evaluate_log_predictions(validation_log, predicted_log)
        row = {
            "alpha": alpha,
            "l1_ratio": l1_ratio,
            "validation_mae": candidate_metrics["mae"],
            "validation_rmse": candidate_metrics["rmse"],
            "validation_r2": candidate_metrics["r2"],
            "fit_seconds": round(perf_counter() - candidate_started, 3),
        }
        tuning_rows.append(row)
        if np.isfinite(row["validation_mae"]) and (
            best is None or row["validation_mae"] < best["validation_mae"]
        ):
            best = row

    if best is None:
        raise RuntimeError("ElasticNet tuning produced no stable candidates.")

    evaluation_model = fit_elasticnet_sgd(
        train_frame=train_frame,
        alpha=float(best["alpha"]),
        l1_ratio=float(best["l1_ratio"]),
        min_frequency=args.categorical_min_frequency,
        random_state=args.random_state,
        max_iter=args.elasticnet_max_iter,
    )
    predicted_log = evaluation_model.predict(test_frame[FEATURE_COLUMNS])
    model = fit_elasticnet_sgd(
        train_frame=data,
        alpha=float(best["alpha"]),
        l1_ratio=float(best["l1_ratio"]),
        min_frequency=args.categorical_min_frequency,
        random_state=args.random_state,
        max_iter=args.elasticnet_max_iter,
    )
    y_test_log = np.log1p(test_frame[TARGET_COLUMN].astype(float))
    metrics = safe_evaluate_log_predictions(y_test_log, predicted_log)
    metrics.update(
        {
            "model": "elasticnet",
            "improved_model": "elasticnet_scaled_tuned",
            "strategy": "scaled numeric features with validation tuning",
            "target": "log1p(price)",
            "rows_in_file_or_read": int(len(raw)),
            "rows_after_cleaning": int(len(cleaned)),
            "rows_used_for_model": int(len(train_frame) + len(test_frame)),
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "fit_seconds": round(perf_counter() - started, 3),
            "best_alpha": float(best["alpha"]),
            "best_l1_ratio": float(best["l1_ratio"]),
            "categorical_min_frequency": args.categorical_min_frequency,
            "validation_size": args.validation_size,
            "candidate_count": len(tuning_rows),
            "refit_on_full_data": True,
            "final_fit_rows": int(len(data)),
            "features": FEATURE_COLUMNS,
            "removed_columns": REMOVED_FEATURES,
            **training_scope_metrics(),
        }
    )
    predictions = prediction_table(test_frame, y_test_log, predicted_log)
    save_forecast_outputs(args.output, "elasticnet", model, metrics, predictions, pd.DataFrame())
    Path(args.output).mkdir(parents=True, exist_ok=True)
    pd.DataFrame(tuning_rows).sort_values("validation_mae").to_csv(
        Path(args.output) / "tuning_results.csv",
        index=False,
        encoding="utf-8",
    )
    joblib.dump(model, Path(args.output) / "elasticnet_scaled_tuned_model.joblib")
    return {"metrics": metrics, "predictions": predictions, "model": model}


def print_metrics(result: dict[str, Any], output: str | Path) -> None:
    metrics = result["metrics"]
    print(f"rows after cleaning: {metrics['rows_after_cleaning']:,}")
    print(f"rows used: {metrics['rows_used_for_model']:,}")
    print(f"MAE: {metrics['mae']:.2f}")
    print(f"RMSE: {metrics['rmse']:.2f}")
    print(f"R2: {metrics['r2']:.3f}")
    print(f"saved to: {Path(output)}")
