"""Train the tuned XGBoost flight price forecast model."""

from __future__ import annotations

import argparse
from pathlib import Path

import xgboost as xgb

from forecast_model_utils import train_sklearn_forecaster


def train_xgboost(args: argparse.Namespace) -> None:
    result = train_sklearn_forecaster(
        model_name="xgboost",
        estimator=xgb.XGBRegressor(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            min_child_weight=args.min_child_weight,
            reg_lambda=args.reg_lambda,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=args.random_state,
            n_jobs=args.n_jobs,
        ),
        input_path=args.input,
        output_dir=args.output,
        sample_size=args.sample_size,
        limit_rows=args.limit_rows,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    metrics = result["metrics"]
    print(f"rows after cleaning: {metrics['rows_after_cleaning']:,}")
    print(f"rows used: {metrics['rows_used_for_model']:,}")
    print(f"MAE: {metrics['mae']:.2f}")
    print(f"RMSE: {metrics['rmse']:.2f}")
    print(f"R2: {metrics['r2']:.3f}")
    print(f"saved to: {Path(args.output)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train tuned XGBoost for flight price forecasting.")
    parser.add_argument("--input", default="etl/exports/flights_features_all.csv")
    parser.add_argument("--output", default="backend/ml/models/xgboost")
    parser.add_argument("--sample-size", type=int, default=0, help="0 uses all cleaned rows before the holdout split.")
    parser.add_argument("--limit-rows", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--n-estimators", type=int, default=420)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.045)
    parser.add_argument("--subsample", type=float, default=0.92)
    parser.add_argument("--colsample-bytree", type=float, default=0.92)
    parser.add_argument("--min-child-weight", type=float, default=1.0)
    parser.add_argument("--reg-lambda", type=float, default=1.0)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    train_xgboost(parse_args())


if __name__ == "__main__":
    main()
