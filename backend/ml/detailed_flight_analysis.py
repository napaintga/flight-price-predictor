"""Detailed EDA/report generator for the flight ticket feature CSV.

Examples:
    python backend/ml/detailed_flight_analysis.py
    python backend/ml/detailed_flight_analysis.py --skip-model --no-plots
    python backend/ml/detailed_flight_analysis.py --limit-rows 5000 --output logs/flight_analysis_check
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from airline_normalization import normalize_airline_value


EXPECTED_COLUMNS = [
    "days_to_departure",
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

NUMERIC_COLUMNS = [
    "days_to_departure",
    "distance_km",
    "passengers_total",
    "stops",
    "duration_minutes",
    "price",
    "depart_hour",
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

CATEGORICAL_COLUMNS = [
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

BINARY_COLUMNS = ["depart_is_weekend", "is_holiday_depart", "search_is_weekend"]

DOW_LABELS = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}

SEASON_LABELS = {
    0: "Winter",
    1: "Spring",
    2: "Summer",
    3: "Autumn",
}

BOOKING_BINS = [-np.inf, 3, 7, 14, 30, 60, 90, np.inf]
BOOKING_LABELS = ["0-3", "4-7", "8-14", "15-30", "31-60", "61-90", "90+"]

DISTANCE_BINS = [0, 500, 1000, 2000, 5000, np.inf]
DISTANCE_LABELS = ["0-500", "500-1000", "1000-2000", "2000-5000", "5000+"]


def log(message: str) -> None:
    print(message, file=sys.stderr)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (np.integer, int)):
        return f"{int(value):,}"
    if isinstance(value, (np.floating, float)):
        if abs(float(value)) >= 1000:
            return f"{float(value):,.2f}"
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    return str(value)


def markdown_table(frame: pd.DataFrame, max_rows: int = 12) -> str:
    if frame is None or frame.empty:
        return "_Немає даних для показу._"

    data = frame.head(max_rows).copy()
    data.columns = [str(col) for col in data.columns]
    headers = [str(col).replace("|", "\\|") for col in data.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in data.iterrows():
        values = [format_value(row[col]).replace("|", "\\|") for col in data.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def save_table(tables_dir: Path, name: str, frame: pd.DataFrame, index: bool = False) -> Path:
    path = tables_dir / f"{name}.csv"
    frame.to_csv(path, index=index, encoding="utf-8")
    return path


def read_dataset(input_path: Path, limit_rows: int | None) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")
    log(f"reading dataset: {input_path}")
    frame = pd.read_csv(input_path, low_memory=False, nrows=limit_rows)
    frame.columns = [str(col).strip() for col in frame.columns]
    log(f"rows loaded: {len(frame):,}; columns: {len(frame.columns):,}")
    return frame


def normalize_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()

    for col in NUMERIC_COLUMNS:
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    if "departure_date" in normalized.columns:
        normalized["departure_date"] = pd.to_datetime(
            normalized["departure_date"],
            errors="coerce",
        )

    for col in CATEGORICAL_COLUMNS:
        if col in normalized.columns:
            values = normalized[col].astype("string").str.strip()
            values = values.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "null": pd.NA})
            normalized[col] = values.fillna("Unknown").astype("object")
    if "travel_class" in normalized.columns:
        normalized["travel_class"] = normalized["travel_class"].map(normalize_travel_class_value)
    if "airline" in normalized.columns:
        normalized["airline"] = normalized["airline"].map(normalize_airline_value)

    for col in BINARY_COLUMNS:
        if col in normalized.columns:
            normalized[col] = normalized[col].where(normalized[col].isin([0, 1]))

    return normalized


def normalize_travel_class_value(value: object) -> str:
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


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()

    if {"origin", "destination"}.issubset(enriched.columns):
        enriched["route"] = enriched["origin"].astype(str) + " -> " + enriched["destination"].astype(str)

    if {"origin_type", "destination_type"}.issubset(enriched.columns):
        enriched["route_type"] = (
            enriched["origin_type"].astype(str) + " -> " + enriched["destination_type"].astype(str)
        )

    if {"price", "distance_km"}.issubset(enriched.columns):
        enriched["price_per_km"] = np.where(
            enriched["distance_km"] > 0,
            enriched["price"] / enriched["distance_km"],
            np.nan,
        )

    if {"price", "duration_minutes"}.issubset(enriched.columns):
        enriched["price_per_hour"] = np.where(
            enriched["duration_minutes"] > 0,
            enriched["price"] / (enriched["duration_minutes"] / 60.0),
            np.nan,
        )

    if {"distance_km", "duration_minutes"}.issubset(enriched.columns):
        enriched["avg_speed_kmh"] = np.where(
            enriched["duration_minutes"] > 0,
            enriched["distance_km"] / (enriched["duration_minutes"] / 60.0),
            np.nan,
        )
        enriched["duration_per_1000km"] = np.where(
            enriched["distance_km"] > 0,
            enriched["duration_minutes"] / enriched["distance_km"] * 1000.0,
            np.nan,
        )

    if {"price", "passengers_total"}.issubset(enriched.columns):
        enriched["revenue_proxy"] = enriched["price"] * enriched["passengers_total"]

    if "stops" in enriched.columns:
        stops = enriched["stops"]
        enriched["is_direct"] = np.where(stops == 0, 1, np.where(stops.notna(), 0, np.nan))
        enriched["stop_bucket"] = np.select(
            [stops.eq(0), stops.eq(1), stops.eq(2), stops.ge(3)],
            ["direct", "1 stop", "2 stops", "3+ stops"],
            default="Unknown",
        )

    if "days_to_departure" in enriched.columns:
        enriched["days_to_departure_bucket"] = pd.cut(
            enriched["days_to_departure"],
            bins=BOOKING_BINS,
            labels=BOOKING_LABELS,
            right=True,
        )

    if "distance_km" in enriched.columns:
        enriched["distance_bucket"] = pd.cut(
            enriched["distance_km"],
            bins=DISTANCE_BINS,
            labels=DISTANCE_LABELS,
            right=True,
            include_lowest=True,
        )

    if "depart_hour" in enriched.columns:
        hour = enriched["depart_hour"]
        enriched["depart_time_bucket"] = np.select(
            [
                hour.between(0, 5, inclusive="both"),
                hour.between(6, 10, inclusive="both"),
                hour.between(11, 16, inclusive="both"),
                hour.between(17, 21, inclusive="both"),
                hour.between(22, 23, inclusive="both"),
            ],
            ["night", "morning", "afternoon", "evening", "late_night"],
            default="Unknown",
        )

    if "depart_dow" in enriched.columns:
        enriched["depart_dow_name"] = enriched["depart_dow"].map(DOW_LABELS).fillna("Unknown")

    if "search_dow" in enriched.columns:
        enriched["search_dow_name"] = enriched["search_dow"].map(DOW_LABELS).fillna("Unknown")

    if "depart_season" in enriched.columns:
        enriched["depart_season_name"] = enriched["depart_season"].map(SEASON_LABELS).fillna("Unknown")

    if "search_season" in enriched.columns:
        enriched["search_season_name"] = enriched["search_season"].map(SEASON_LABELS).fillna("Unknown")

    if "price" in enriched.columns:
        valid_price = enriched["price"].where(enriched["price"] > 0)
        try:
            enriched["price_segment"] = pd.qcut(
                valid_price,
                q=[0, 0.33, 0.66, 1.0],
                labels=["low", "middle", "premium"],
                duplicates="drop",
            )
        except ValueError:
            enriched["price_segment"] = pd.NA

    return enriched


def build_valid_mask(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    checks = {
        "price": frame["price"] > 0 if "price" in frame.columns else True,
        "distance_km": frame["distance_km"] > 0 if "distance_km" in frame.columns else True,
        "duration_minutes": frame["duration_minutes"] > 0 if "duration_minutes" in frame.columns else True,
        "days_to_departure": frame["days_to_departure"] >= 0 if "days_to_departure" in frame.columns else True,
        "stops": frame["stops"] >= 0 if "stops" in frame.columns else True,
        "passengers_total": frame["passengers_total"] > 0 if "passengers_total" in frame.columns else True,
    }
    for check in checks.values():
        if isinstance(check, pd.Series):
            mask &= check.fillna(False)
    return mask


def anomaly_count(frame: pd.DataFrame, condition: pd.Series | np.ndarray | bool) -> int:
    if isinstance(condition, bool):
        return int(condition) * len(frame)
    return int(pd.Series(condition, index=frame.index).fillna(False).sum())


def quality_tables(frame: pd.DataFrame, valid_mask: pd.Series) -> dict[str, pd.DataFrame]:
    missing_columns = [col for col in EXPECTED_COLUMNS if col not in frame.columns]
    missing_summary = pd.DataFrame(
        {
            "column": list(frame.columns),
            "missing_rows": [int(frame[col].isna().sum()) for col in frame.columns],
            "missing_pct": [float(frame[col].isna().mean() * 100.0) for col in frame.columns],
        }
    ).sort_values(["missing_rows", "column"], ascending=[False, True])

    duplicate_rows = int(frame.duplicated().sum())
    duplicate_flight_id = 0
    if "flight_id" in frame.columns:
        duplicate_flight_id = int(frame.loc[frame["flight_id"] != "Unknown", "flight_id"].duplicated().sum())

    key_cols = [
        "origin",
        "destination",
        "departure_date",
        "departure_time",
        "arrival_time",
        "airline",
        "travel_class",
        "price",
    ]
    available_key_cols = [col for col in key_cols if col in frame.columns]
    duplicate_ticket_key = (
        int(frame.duplicated(subset=available_key_cols).sum()) if available_key_cols else 0
    )

    anomalies = [
        {
            "check": "Rows rejected by validity filter",
            "rows": int((~valid_mask).sum()),
            "share_pct": float((~valid_mask).mean() * 100.0),
        },
        {
            "check": "Duplicate full rows",
            "rows": duplicate_rows,
            "share_pct": float(duplicate_rows / max(len(frame), 1) * 100.0),
        },
        {
            "check": "Duplicate flight_id values",
            "rows": duplicate_flight_id,
            "share_pct": float(duplicate_flight_id / max(len(frame), 1) * 100.0),
        },
        {
            "check": "Duplicate ticket-like key",
            "rows": duplicate_ticket_key,
            "share_pct": float(duplicate_ticket_key / max(len(frame), 1) * 100.0),
        },
    ]

    simple_checks: list[tuple[str, str, pd.Series]] = []
    if "price" in frame.columns:
        simple_checks.append(("Non-positive price", "price", frame["price"] <= 0))
    if "distance_km" in frame.columns:
        simple_checks.append(("Non-positive distance_km", "distance_km", frame["distance_km"] <= 0))
    if "duration_minutes" in frame.columns:
        simple_checks.append(
            ("Non-positive duration_minutes", "duration_minutes", frame["duration_minutes"] <= 0)
        )
    if "days_to_departure" in frame.columns:
        simple_checks.append(
            ("Negative days_to_departure", "days_to_departure", frame["days_to_departure"] < 0)
        )
    if "stops" in frame.columns:
        simple_checks.append(("Negative stops", "stops", frame["stops"] < 0))
    if "passengers_total" in frame.columns:
        simple_checks.append(
            ("Non-positive passengers_total", "passengers_total", frame["passengers_total"] <= 0)
        )
    if "avg_speed_kmh" in frame.columns:
        simple_checks.append(
            (
                "Suspicious avg_speed_kmh below 100",
                "avg_speed_kmh",
                frame["avg_speed_kmh"].between(0, 100, inclusive="left"),
            )
        )
        simple_checks.append(
            ("Suspicious avg_speed_kmh above 1200", "avg_speed_kmh", frame["avg_speed_kmh"] > 1200)
        )
    if {"distance_km", "stops"}.issubset(frame.columns):
        simple_checks.append(
            (
                "Short route with 2+ stops",
                "distance_km/stops",
                (frame["distance_km"] < 500) & (frame["stops"] >= 2),
            )
        )

    if "price_per_km" in frame.columns:
        price_per_km = frame.loc[valid_mask, "price_per_km"].dropna()
        if not price_per_km.empty:
            q1, q3 = price_per_km.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                simple_checks.append(
                    (
                        "High price_per_km outlier by 3*IQR",
                        "price_per_km",
                        frame["price_per_km"] > q3 + 3 * iqr,
                    )
                )

    for label, column, condition in simple_checks:
        rows = anomaly_count(frame, condition)
        anomalies.append(
            {
                "check": label,
                "rows": rows,
                "share_pct": float(rows / max(len(frame), 1) * 100.0),
                "column": column,
            }
        )

    return {
        "missing_values": missing_summary,
        "missing_expected_columns": pd.DataFrame({"missing_column": missing_columns}),
        "quality_anomalies": pd.DataFrame(anomalies).fillna(""),
    }


def overview_table(raw: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    date_min = valid["departure_date"].min() if "departure_date" in valid.columns else pd.NaT
    date_max = valid["departure_date"].max() if "departure_date" in valid.columns else pd.NaT

    rows = [
        ("raw_rows", len(raw)),
        ("valid_rows", len(valid)),
        ("dropped_rows", len(raw) - len(valid)),
        ("columns", len(raw.columns)),
        ("unique_flights", valid["flight_id"].nunique() if "flight_id" in valid.columns else np.nan),
        ("unique_routes", valid["route"].nunique() if "route" in valid.columns else np.nan),
        ("unique_airlines", valid["airline"].nunique() if "airline" in valid.columns else np.nan),
        ("departure_date_min", date_min.date().isoformat() if pd.notna(date_min) else ""),
        ("departure_date_max", date_max.date().isoformat() if pd.notna(date_max) else ""),
        ("avg_price", valid["price"].mean() if "price" in valid.columns else np.nan),
        ("median_price", valid["price"].median() if "price" in valid.columns else np.nan),
        ("min_price", valid["price"].min() if "price" in valid.columns else np.nan),
        ("max_price", valid["price"].max() if "price" in valid.columns else np.nan),
        ("avg_distance_km", valid["distance_km"].mean() if "distance_km" in valid.columns else np.nan),
        (
            "avg_duration_minutes",
            valid["duration_minutes"].mean() if "duration_minutes" in valid.columns else np.nan,
        ),
        (
            "total_passengers",
            valid["passengers_total"].sum() if "passengers_total" in valid.columns else np.nan,
        ),
        (
            "revenue_proxy",
            valid["revenue_proxy"].sum() if "revenue_proxy" in valid.columns else np.nan,
        ),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def price_metrics_table(valid: pd.DataFrame) -> pd.DataFrame:
    if "price" not in valid.columns:
        return pd.DataFrame()
    price = valid["price"].dropna()
    if price.empty:
        return pd.DataFrame()

    metrics = {
        "count": price.count(),
        "mean": price.mean(),
        "median": price.median(),
        "std": price.std(),
        "min": price.min(),
        "q25": price.quantile(0.25),
        "q75": price.quantile(0.75),
        "p90": price.quantile(0.90),
        "p95": price.quantile(0.95),
        "p99": price.quantile(0.99),
        "max": price.max(),
        "coefficient_of_variation": price.std() / price.mean() if price.mean() else np.nan,
    }
    return pd.DataFrame(metrics.items(), columns=["metric", "value"])


def numeric_describe_table(valid: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [col for col in NUMERIC_COLUMNS if col in valid.columns]
    derived_cols = [
        "price_per_km",
        "price_per_hour",
        "avg_speed_kmh",
        "duration_per_1000km",
        "revenue_proxy",
    ]
    numeric_cols += [col for col in derived_cols if col in valid.columns]
    if not numeric_cols:
        return pd.DataFrame()
    return valid[numeric_cols].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).T.reset_index(
        names="column"
    )


def categorical_frequency_table(valid: pd.DataFrame, column: str, limit: int = 30) -> pd.DataFrame:
    if column not in valid.columns:
        return pd.DataFrame()
    counts = valid[column].value_counts(dropna=False).head(limit).reset_index()
    counts.columns = [column, "records"]
    counts["share_pct"] = counts["records"] / max(len(valid), 1) * 100.0
    return counts


def group_summary(
    valid: pd.DataFrame,
    group_cols: str | list[str],
    sort_col: str = "records",
    ascending: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    if any(col not in valid.columns for col in group_cols) or "price" not in valid.columns:
        return pd.DataFrame()

    grouped = (
        valid.groupby(group_cols, dropna=False, observed=False)
        .agg(
            records=("price", "size"),
            total_passengers=("passengers_total", "sum"),
            avg_price=("price", "mean"),
            median_price=("price", "median"),
            p90_price=("price", lambda s: s.quantile(0.90)),
            avg_distance_km=("distance_km", "mean"),
            avg_duration_minutes=("duration_minutes", "mean"),
            avg_stops=("stops", "mean"),
            avg_price_per_km=("price_per_km", "mean"),
            median_price_per_km=("price_per_km", "median"),
            avg_price_per_hour=("price_per_hour", "mean"),
            total_revenue_proxy=("revenue_proxy", "sum"),
        )
        .reset_index()
    )
    if sort_col in grouped.columns:
        grouped = grouped.sort_values(sort_col, ascending=ascending)
    if limit is not None:
        grouped = grouped.head(limit)
    return grouped


def route_efficiency_table(valid: pd.DataFrame, limit: int | None = 100) -> pd.DataFrame:
    if "route" not in valid.columns:
        return pd.DataFrame()
    result = group_summary(valid, "route", sort_col="total_passengers", ascending=False, limit=limit)
    if result.empty:
        return result
    if "is_direct" in valid.columns:
        result["direct_share_pct"] = (
            valid.groupby("route", dropna=False, observed=False)["is_direct"]
            .mean()
            .reindex(result["route"])
            .to_numpy()
            * 100.0
        )
    if "duration_per_1000km" in valid.columns:
        result["avg_duration_per_1000km"] = (
            valid.groupby("route", dropna=False, observed=False)["duration_per_1000km"]
            .mean()
            .reindex(result["route"])
            .to_numpy()
        )
    return result


def pivot_table(
    valid: pd.DataFrame,
    index: str,
    columns: str,
    values: str,
    aggfunc: str = "median",
) -> pd.DataFrame:
    needed = {index, columns, values}
    if not needed.issubset(valid.columns):
        return pd.DataFrame()
    pivot = pd.pivot_table(
        valid,
        index=index,
        columns=columns,
        values=values,
        aggfunc=aggfunc,
        observed=False,
    )
    return pivot.reset_index()


def correlation_table(valid: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "price",
        "days_to_departure",
        "distance_km",
        "duration_minutes",
        "passengers_total",
        "depart_hour",
        "stops",
        "price_per_km",
        "price_per_hour",
        "avg_speed_kmh",
        "revenue_proxy",
    ]
    available = [col for col in cols if col in valid.columns]
    if len(available) < 2:
        return pd.DataFrame()
    return valid[available].corr(numeric_only=True).round(4).reset_index(names="metric")


def anomaly_examples(valid: pd.DataFrame) -> dict[str, pd.DataFrame]:
    base_cols = [
        "flight_id",
        "route",
        "airline",
        "travel_class",
        "days_to_departure",
        "stops",
        "distance_km",
        "duration_minutes",
        "price",
        "price_per_km",
        "price_per_hour",
        "avg_speed_kmh",
        "depart_season_name",
        "is_holiday_depart",
    ]
    cols = [col for col in base_cols if col in valid.columns]
    result: dict[str, pd.DataFrame] = {}
    if "price_per_km" in valid.columns:
        result["anomaly_high_price_per_km"] = valid.nlargest(100, "price_per_km")[cols]
    if "price" in valid.columns:
        result["anomaly_high_price"] = valid.nlargest(100, "price")[cols]
        result["anomaly_low_positive_price"] = valid.nsmallest(100, "price")[cols]
    if "avg_speed_kmh" in valid.columns:
        result["anomaly_low_speed"] = valid.nsmallest(100, "avg_speed_kmh")[cols]
        result["anomaly_high_speed"] = valid.nlargest(100, "avg_speed_kmh")[cols]
    return result


def statistical_tests(valid: pd.DataFrame, sample_size: int, random_state: int) -> pd.DataFrame:
    try:
        from scipy import stats
    except Exception as exc:  # pragma: no cover - optional dependency guard
        return pd.DataFrame([{"test": "scipy_unavailable", "note": str(exc)}])

    if "price" not in valid.columns:
        return pd.DataFrame()

    sample = valid.dropna(subset=["price"])
    if len(sample) > sample_size:
        sample = sample.sample(sample_size, random_state=random_state)

    rows: list[dict[str, Any]] = []

    def add_binary_tests(column: str, label: str) -> None:
        if column not in sample.columns:
            return
        group0 = sample.loc[sample[column] == 0, "price"].dropna()
        group1 = sample.loc[sample[column] == 1, "price"].dropna()
        if len(group0) < 2 or len(group1) < 2:
            return
        t_stat, t_pvalue = stats.ttest_ind(group1, group0, equal_var=False, nan_policy="omit")
        mw_stat, mw_pvalue = stats.mannwhitneyu(group1, group0, alternative="two-sided")
        rows.append(
            {
                "test": f"{label}: Welch t-test",
                "group_0_n": len(group0),
                "group_1_n": len(group1),
                "group_0_mean": group0.mean(),
                "group_1_mean": group1.mean(),
                "group_0_median": group0.median(),
                "group_1_median": group1.median(),
                "statistic": t_stat,
                "p_value": t_pvalue,
            }
        )
        rows.append(
            {
                "test": f"{label}: Mann-Whitney U",
                "group_0_n": len(group0),
                "group_1_n": len(group1),
                "group_0_mean": group0.mean(),
                "group_1_mean": group1.mean(),
                "group_0_median": group0.median(),
                "group_1_median": group1.median(),
                "statistic": mw_stat,
                "p_value": mw_pvalue,
            }
        )

    def add_kruskal(column: str, label: str) -> None:
        if column not in sample.columns:
            return
        groups = []
        group_names = []
        for name, group in sample.groupby(column, dropna=True):
            values = group["price"].dropna()
            if len(values) >= 2:
                groups.append(values)
                group_names.append(str(name))
        if len(groups) < 2 or len(groups) > 50:
            return
        stat, pvalue = stats.kruskal(*groups)
        rows.append(
            {
                "test": f"{label}: Kruskal-Wallis",
                "groups": ", ".join(group_names[:20]),
                "group_count": len(groups),
                "statistic": stat,
                "p_value": pvalue,
            }
        )

    add_binary_tests("is_holiday_depart", "Holiday vs non-holiday departure")
    add_binary_tests("depart_is_weekend", "Weekend vs weekday departure")
    add_binary_tests("search_is_weekend", "Weekend vs weekday search")

    add_kruskal("depart_dow_name", "Departure day of week")
    add_kruskal("depart_season_name", "Departure season")
    add_kruskal("travel_class", "Travel class")
    add_kruskal("stop_bucket", "Stops")

    if {"trip_type", "travel_class"}.issubset(sample.columns):
        cross = pd.crosstab(sample["trip_type"], sample["travel_class"])
        if min(cross.shape) >= 2:
            chi2, pvalue, dof, _ = stats.chi2_contingency(cross)
            rows.append(
                {
                    "test": "trip_type x travel_class: chi-square",
                    "degrees_of_freedom": dof,
                    "statistic": chi2,
                    "p_value": pvalue,
                }
            )

    if {"depart_season_name", "stop_bucket"}.issubset(sample.columns):
        cross = pd.crosstab(sample["depart_season_name"], sample["stop_bucket"])
        if min(cross.shape) >= 2:
            chi2, pvalue, dof, _ = stats.chi2_contingency(cross)
            rows.append(
                {
                    "test": "depart_season x stops: chi-square",
                    "degrees_of_freedom": dof,
                    "statistic": chi2,
                    "p_value": pvalue,
                }
            )

    return pd.DataFrame(rows)


def run_price_model(
    valid: pd.DataFrame,
    sample_size: int,
    random_state: int,
    n_jobs: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder
    except Exception as exc:  # pragma: no cover - optional dependency guard
        return (
            pd.DataFrame([{"metric": "sklearn_unavailable", "value": str(exc)}]),
            pd.DataFrame(),
            pd.DataFrame(),
        )

    numeric_features = [
        "days_to_departure",
        "stops",
        "duration_minutes",
        "distance_km",
        "depart_hour",
    ]
    categorical_features = [
        "travel_class",
        "airline",
        "origin",
        "destination",
        "arrival_time",
        "depart_dow_name",
        "depart_month",
        "search_month",
    ]

    numeric_features = [col for col in numeric_features if col in valid.columns]
    categorical_features = [col for col in categorical_features if col in valid.columns]
    feature_cols = numeric_features + categorical_features
    if not feature_cols or "price" not in valid.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    model_data = valid.loc[valid["price"] > 0, feature_cols + ["price"]].copy()
    if len(model_data) < 100:
        return (
            pd.DataFrame([{"metric": "skipped", "value": "not enough rows for model"}]),
            pd.DataFrame(),
            pd.DataFrame(),
        )
    if len(model_data) > sample_size:
        model_data = model_data.sample(sample_size, random_state=random_state)

    for col in categorical_features:
        model_data[col] = model_data[col].astype("string").fillna("Unknown")

    x = model_data[feature_cols]
    y_log = np.log1p(model_data["price"].astype(float))
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y_log,
        test_size=0.2,
        random_state=random_state,
    )

    try:
        encoder = OneHotEncoder(
            handle_unknown="infrequent_if_exist",
            min_frequency=25,
            sparse_output=True,
        )
    except TypeError:
        encoder = OneHotEncoder(handle_unknown="ignore")

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), numeric_features),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", encoder),
                    ]
                ),
                categorical_features,
            ),
        ],
        remainder="drop",
    )

    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=16,
        min_samples_leaf=20,
        n_jobs=n_jobs,
        random_state=random_state,
    )
    pipeline = Pipeline(steps=[("prep", preprocessor), ("model", model)])
    pipeline.fit(x_train, y_train)

    predicted_log = pipeline.predict(x_test)
    y_test_price = np.expm1(y_test)
    predicted_price = np.maximum(np.expm1(predicted_log), 0)
    baseline_price = np.full_like(y_test_price, fill_value=np.median(np.expm1(y_train)), dtype=float)

    metrics = pd.DataFrame(
        [
            {"metric": "rows_used", "value": len(model_data)},
            {"metric": "features_used", "value": len(feature_cols)},
            {"metric": "target", "value": "log1p(price)"},
            {"metric": "model", "value": "RandomForestRegressor"},
            {"metric": "mae", "value": mean_absolute_error(y_test_price, predicted_price)},
            {"metric": "rmse", "value": np.sqrt(mean_squared_error(y_test_price, predicted_price))},
            {"metric": "r2", "value": r2_score(y_test_price, predicted_price)},
            {
                "metric": "baseline_median_mae",
                "value": mean_absolute_error(y_test_price, baseline_price),
            },
        ]
    )

    try:
        feature_names = pipeline.named_steps["prep"].get_feature_names_out()
    except Exception:
        feature_names = np.array(feature_cols, dtype=object)

    importances = pipeline.named_steps["model"].feature_importances_
    detail = pd.DataFrame(
        {
            "feature": feature_names[: len(importances)],
            "importance": importances,
        }
    ).sort_values("importance", ascending=False)

    cleaned_names = detail["feature"].astype(str).str.replace(r"^(num|cat)__", "", regex=True)
    source_rows = []
    for source in feature_cols:
        mask = cleaned_names.eq(source) | cleaned_names.str.startswith(source + "_")
        source_rows.append(
            {
                "source_feature": source,
                "importance": detail.loc[mask, "importance"].sum(),
            }
        )
    source_importance = pd.DataFrame(source_rows).sort_values("importance", ascending=False)

    return metrics, source_importance, detail.head(200)


def maybe_import_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except Exception as exc:  # pragma: no cover - optional dependency guard
        log(f"plots skipped: matplotlib is unavailable ({exc})")
        return None


def save_histogram(plt: Any, series: pd.Series, title: str, xlabel: str, path: Path, bins: int = 60) -> Path:
    values = series.dropna()
    if values.empty:
        return path
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(values, bins=bins, color="#348AA7", edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Records")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_bar_chart(
    plt: Any,
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    ylabel: str,
    path: Path,
    rotate: int = 35,
) -> Path:
    if frame.empty or x_col not in frame.columns or y_col not in frame.columns:
        return path
    data = frame[[x_col, y_col]].dropna().copy()
    if data.empty:
        return path
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(data[x_col].astype(str), data[y_col], color="#5B8E7D")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=rotate)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_line_chart(
    plt: Any,
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    ylabel: str,
    path: Path,
) -> Path:
    if frame.empty or x_col not in frame.columns or y_col not in frame.columns:
        return path
    data = frame[[x_col, y_col]].dropna().sort_values(x_col)
    if data.empty:
        return path
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(data[x_col], data[y_col], color="#D1495B", linewidth=2)
    ax.scatter(data[x_col], data[y_col], color="#D1495B", s=18)
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_scatter_chart(
    plt: Any,
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    path: Path,
    sample_size: int,
    random_state: int,
) -> Path:
    if frame.empty or x_col not in frame.columns or y_col not in frame.columns:
        return path
    data = frame[[x_col, y_col]].dropna()
    if len(data) > sample_size:
        data = data.sample(sample_size, random_state=random_state)
    if data.empty:
        return path
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(data[x_col], data[y_col], alpha=0.18, s=10, color="#4A6FA5")
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_heatmap(plt: Any, matrix: pd.DataFrame, title: str, path: Path) -> Path:
    if matrix.empty:
        return path
    data = matrix.set_index(matrix.columns[0])
    if data.empty:
        return path
    numeric = data.apply(pd.to_numeric, errors="coerce")
    if numeric.dropna(how="all").empty:
        return path

    fig_width = max(8, min(18, 1.0 + len(numeric.columns) * 0.8))
    fig_height = max(5, min(14, 1.5 + len(numeric.index) * 0.45))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(numeric.to_numpy(dtype=float), aspect="auto", cmap="viridis")
    ax.set_title(title)
    ax.set_xticks(np.arange(len(numeric.columns)))
    ax.set_xticklabels([str(col) for col in numeric.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(numeric.index)))
    ax.set_yticklabels([str(idx) for idx in numeric.index])
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def build_charts(
    valid: pd.DataFrame,
    charts_dir: Path,
    tables: dict[str, pd.DataFrame],
    sample_size: int,
    random_state: int,
) -> list[Path]:
    plt = maybe_import_matplotlib()
    if plt is None:
        return []

    paths: list[Path] = []
    if "price" in valid.columns:
        clipped_price = valid["price"].clip(upper=valid["price"].quantile(0.99))
        paths.append(
            save_histogram(
                plt,
                clipped_price,
                "Price distribution clipped at p99",
                "price",
                charts_dir / "price_histogram.png",
            )
        )
        paths.append(
            save_histogram(
                plt,
                np.log1p(valid["price"]),
                "Log price distribution",
                "log1p(price)",
                charts_dir / "log_price_histogram.png",
            )
        )

    if "price_by_days_to_departure" in tables:
        paths.append(
            save_line_chart(
                plt,
                tables["price_by_days_to_departure"],
                "days_to_departure",
                "median_price",
                "Median price by days to departure",
                "Median price",
                charts_dir / "median_price_by_days_to_departure.png",
            )
        )

    chart_specs = [
        (
            "price_by_travel_class",
            "travel_class",
            "median_price",
            "Median price by travel class",
            "Median price",
            "median_price_by_travel_class.png",
        ),
        (
            "price_by_stop_bucket",
            "stop_bucket",
            "median_price",
            "Median price by stops",
            "Median price",
            "median_price_by_stops.png",
        ),
        (
            "price_by_depart_season_name",
            "depart_season_name",
            "median_price",
            "Median price by season",
            "Median price",
            "median_price_by_season.png",
        ),
        (
            "demand_by_airline",
            "airline",
            "total_passengers",
            "Passengers by airline",
            "Passengers",
            "passengers_by_airline.png",
        ),
        (
            "top_routes_by_passengers",
            "route",
            "total_passengers",
            "Top routes by passengers",
            "Passengers",
            "top_routes_by_passengers.png",
        ),
    ]
    for table_name, x_col, y_col, title, ylabel, filename in chart_specs:
        if table_name in tables:
            paths.append(
                save_bar_chart(
                    plt,
                    tables[table_name].head(20),
                    x_col,
                    y_col,
                    title,
                    ylabel,
                    charts_dir / filename,
                )
            )

    if {"distance_km", "price"}.issubset(valid.columns):
        paths.append(
            save_scatter_chart(
                plt,
                valid,
                "distance_km",
                "price",
                "Distance vs price",
                charts_dir / "distance_vs_price.png",
                sample_size,
                random_state,
            )
        )

    if "heatmap_depart_dow_hour_avg_price" in tables:
        paths.append(
            save_heatmap(
                plt,
                tables["heatmap_depart_dow_hour_avg_price"],
                "Average price by departure day and hour",
                charts_dir / "heatmap_depart_dow_hour_avg_price.png",
            )
        )
    if "pivot_season_booking_median_price" in tables:
        paths.append(
            save_heatmap(
                plt,
                tables["pivot_season_booking_median_price"],
                "Median price by season and booking window",
                charts_dir / "heatmap_season_booking_median_price.png",
            )
        )

    return [path for path in paths if path.exists()]


def add_table(
    tables: dict[str, pd.DataFrame],
    tables_dir: Path,
    name: str,
    frame: pd.DataFrame,
    index: bool = False,
) -> None:
    tables[name] = frame
    save_table(tables_dir, name, frame, index=index)


def build_analysis_tables(raw: pd.DataFrame, valid: pd.DataFrame, tables_dir: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}

    add_table(tables, tables_dir, "overview", overview_table(raw, valid))
    add_table(tables, tables_dir, "price_metrics", price_metrics_table(valid))
    add_table(tables, tables_dir, "numeric_describe", numeric_describe_table(valid))

    valid_mask = build_valid_mask(raw)
    for name, frame in quality_tables(raw, valid_mask).items():
        add_table(tables, tables_dir, name, frame)

    for column in [
        "airline",
        "travel_class",
        "trip_type",
        "origin_type",
        "destination_type",
        "depart_season_name",
        "search_season_name",
        "depart_dow_name",
        "search_dow_name",
        "departure_time",
        "arrival_time",
    ]:
        add_table(tables, tables_dir, f"frequency_{column}", categorical_frequency_table(valid, column))

    price_dimensions = [
        ("airline", "records", False, 100),
        ("travel_class", "records", False, None),
        ("trip_type", "records", False, None),
        ("stops", "stops", True, None),
        ("stop_bucket", "records", False, None),
        ("depart_dow_name", "depart_dow_name", True, None),
        ("depart_month", "depart_month", True, None),
        ("depart_season_name", "records", False, None),
        ("is_holiday_depart", "is_holiday_depart", True, None),
        ("depart_is_weekend", "depart_is_weekend", True, None),
        ("search_is_weekend", "search_is_weekend", True, None),
        ("origin_type", "records", False, None),
        ("destination_type", "records", False, None),
        ("route_type", "records", False, None),
        ("distance_bucket", "distance_bucket", True, None),
        ("days_to_departure_bucket", "days_to_departure_bucket", True, None),
        ("depart_time_bucket", "depart_time_bucket", True, None),
        ("price_segment", "price_segment", True, None),
        ("is_direct", "is_direct", True, None),
    ]
    for column, sort_col, ascending, limit in price_dimensions:
        table = group_summary(valid, column, sort_col=sort_col, ascending=ascending, limit=limit)
        add_table(tables, tables_dir, f"price_by_{column}", table)

    if "days_to_departure" in valid.columns:
        add_table(
            tables,
            tables_dir,
            "price_by_days_to_departure",
            group_summary(
                valid,
                "days_to_departure",
                sort_col="days_to_departure",
                ascending=True,
                limit=None,
            ),
        )

    add_table(tables, tables_dir, "top_routes_by_passengers", route_efficiency_table(valid, limit=100))
    add_table(
        tables,
        tables_dir,
        "top_routes_by_revenue",
        group_summary(valid, "route", sort_col="total_revenue_proxy", ascending=False, limit=100),
    )
    add_table(
        tables,
        tables_dir,
        "top_routes_by_price_per_km",
        group_summary(valid, "route", sort_col="avg_price_per_km", ascending=False, limit=100),
    )
    add_table(
        tables,
        tables_dir,
        "demand_by_airline",
        group_summary(valid, "airline", sort_col="total_passengers", ascending=False, limit=100),
    )
    add_table(
        tables,
        tables_dir,
        "demand_by_travel_class",
        group_summary(valid, "travel_class", sort_col="total_passengers", ascending=False),
    )
    add_table(
        tables,
        tables_dir,
        "demand_by_trip_type",
        group_summary(valid, "trip_type", sort_col="total_passengers", ascending=False),
    )
    add_table(
        tables,
        tables_dir,
        "demand_by_search_dow",
        group_summary(valid, "search_dow_name", sort_col="total_passengers", ascending=False),
    )
    add_table(
        tables,
        tables_dir,
        "demand_by_search_month",
        group_summary(valid, "search_month", sort_col="search_month", ascending=True),
    )

    pivots = {
        "pivot_class_stops_median_price": ("travel_class", "stop_bucket", "price", "median"),
        "pivot_season_booking_median_price": (
            "depart_season_name",
            "days_to_departure_bucket",
            "price",
            "median",
        ),
        "pivot_airline_distance_median_price": ("airline", "distance_bucket", "price", "median"),
        "pivot_depart_month_class_avg_price": ("depart_month", "travel_class", "price", "mean"),
        "pivot_search_depart_dow_count": ("search_dow_name", "depart_dow_name", "price", "count"),
        "heatmap_depart_dow_hour_avg_price": ("depart_dow_name", "depart_hour", "price", "mean"),
        "pivot_holiday_weekend_avg_price": (
            "is_holiday_depart",
            "depart_is_weekend",
            "price",
            "mean",
        ),
        "pivot_top_routes_season_passengers": (
            "route",
            "depart_season_name",
            "passengers_total",
            "sum",
        ),
    }
    for name, (index, columns, values, aggfunc) in pivots.items():
        table_input = valid
        if name == "pivot_top_routes_season_passengers" and "route" in valid.columns:
            top_routes = (
                tables["top_routes_by_passengers"]["route"].head(20).tolist()
                if "top_routes_by_passengers" in tables and "route" in tables["top_routes_by_passengers"].columns
                else []
            )
            table_input = valid[valid["route"].isin(top_routes)] if top_routes else valid
        add_table(tables, tables_dir, name, pivot_table(table_input, index, columns, values, aggfunc))

    add_table(tables, tables_dir, "correlation_matrix", correlation_table(valid))

    for name, frame in anomaly_examples(valid).items():
        add_table(tables, tables_dir, name, frame)

    return tables


def get_table_value(frame: pd.DataFrame, column: str, key: Any, metric: str) -> float | None:
    if frame.empty or column not in frame.columns or metric not in frame.columns:
        return None
    match = frame.loc[frame[column].astype(str) == str(key), metric]
    if match.empty:
        return None
    value = match.iloc[0]
    return float(value) if pd.notna(value) else None


def pct_change(new: float | None, base: float | None) -> float | None:
    if new is None or base in (None, 0):
        return None
    return (new / base - 1.0) * 100.0


def build_insights(tables: dict[str, pd.DataFrame]) -> list[str]:
    insights: list[str] = []

    booking = tables.get("price_by_days_to_departure_bucket", pd.DataFrame())
    if not booking.empty and "median_price" in booking.columns:
        cheapest = booking.sort_values("median_price").head(1).iloc[0]
        insights.append(
            f"Найнижча медіанна ціна у вікні бронювання `{cheapest['days_to_departure_bucket']}`: "
            f"{format_value(cheapest['median_price'])}."
        )

    holiday = tables.get("price_by_is_holiday_depart", pd.DataFrame())
    holiday_premium = pct_change(
        get_table_value(holiday, "is_holiday_depart", 1, "median_price"),
        get_table_value(holiday, "is_holiday_depart", 0, "median_price"),
    )
    if holiday_premium is not None:
        insights.append(f"Святкова медіанна націнка: {holiday_premium:.1f}% відносно не святкових дат.")

    weekend = tables.get("price_by_depart_is_weekend", pd.DataFrame())
    weekend_premium = pct_change(
        get_table_value(weekend, "depart_is_weekend", 1, "median_price"),
        get_table_value(weekend, "depart_is_weekend", 0, "median_price"),
    )
    if weekend_premium is not None:
        insights.append(f"Медіанна різниця для вильотів у вихідні: {weekend_premium:.1f}%.")

    direct = tables.get("price_by_is_direct", pd.DataFrame())
    direct_premium = pct_change(
        get_table_value(direct, "is_direct", 1.0, "median_price"),
        get_table_value(direct, "is_direct", 0.0, "median_price"),
    )
    if direct_premium is not None:
        insights.append(f"Медіанна різниця прямих рейсів проти непрямих: {direct_premium:.1f}%.")

    routes = tables.get("top_routes_by_passengers", pd.DataFrame())
    if not routes.empty and "route" in routes.columns:
        top = routes.iloc[0]
        insights.append(
            f"Найпопулярніший маршрут: `{top['route']}` з {format_value(top['total_passengers'])} пасажирами."
        )

    revenue_routes = tables.get("top_routes_by_revenue", pd.DataFrame())
    if not revenue_routes.empty and "route" in revenue_routes.columns:
        top = revenue_routes.iloc[0]
        insights.append(
            f"Найбільший revenue proxy дає маршрут `{top['route']}`: "
            f"{format_value(top['total_revenue_proxy'])}."
        )

    correlations = tables.get("correlation_matrix", pd.DataFrame())
    if not correlations.empty and "metric" in correlations.columns and "price" in correlations.columns:
        price_corr = correlations.set_index("metric")["price"].drop(labels=["price"], errors="ignore")
        price_corr = price_corr.drop(labels=["revenue_proxy", "price_per_km", "price_per_hour"], errors="ignore")
        price_corr = price_corr.dropna()
        if not price_corr.empty:
            strongest = price_corr.abs().sort_values(ascending=False).index[0]
            insights.append(
                f"Найсильніша проста числова кореляція з ціною: `{strongest}` "
                f"({price_corr.loc[strongest]:.3f})."
            )

    model_importance = tables.get("model_feature_importance", pd.DataFrame())
    if not model_importance.empty and "source_feature" in model_importance.columns:
        top = model_importance.iloc[0]
        insights.append(
            f"У моделі найважливіший фактор: `{top['source_feature']}` "
            f"(importance {top['importance']:.3f})."
        )

    return insights


def write_report(
    output_dir: Path,
    input_path: Path,
    tables: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    model_skipped: bool,
) -> Path:
    report_path = output_dir / "report.md"
    insights = build_insights(tables)

    lines = [
        "# Детальний аналіз авіаквитків",
        "",
        f"Згенеровано: {datetime.now().isoformat(timespec='seconds')}",
        f"Джерело даних: `{input_path}`",
        "",
        "## Ключові автоматичні висновки",
        "",
    ]
    if insights:
        lines.extend([f"- {insight}" for insight in insights])
    else:
        lines.append("- Недостатньо даних для автоматичних висновків.")

    lines.extend(
        [
            "",
            "## Огляд даних",
            "",
            markdown_table(tables.get("overview", pd.DataFrame())),
            "",
            "## Якість даних та аномалії",
            "",
            markdown_table(tables.get("quality_anomalies", pd.DataFrame()), max_rows=20),
            "",
            "### Найбільші пропуски",
            "",
            markdown_table(tables.get("missing_values", pd.DataFrame()), max_rows=12),
            "",
            "## Метрики ціни",
            "",
            markdown_table(tables.get("price_metrics", pd.DataFrame()), max_rows=20),
            "",
            "## Ціна за ключовими категоріями",
            "",
            "### Клас подорожі",
            "",
            markdown_table(tables.get("price_by_travel_class", pd.DataFrame()), max_rows=12),
            "",
            "### Пересадки",
            "",
            markdown_table(tables.get("price_by_stop_bucket", pd.DataFrame()), max_rows=12),
            "",
            "### Сезон вильоту",
            "",
            markdown_table(tables.get("price_by_depart_season_name", pd.DataFrame()), max_rows=12),
            "",
            "### Вікно бронювання",
            "",
            markdown_table(tables.get("price_by_days_to_departure_bucket", pd.DataFrame()), max_rows=12),
            "",
            "## Попит і маршрути",
            "",
            "### Top маршрути за пасажирами",
            "",
            markdown_table(tables.get("top_routes_by_passengers", pd.DataFrame()), max_rows=15),
            "",
            "### Top маршрути за revenue proxy",
            "",
            markdown_table(tables.get("top_routes_by_revenue", pd.DataFrame()), max_rows=15),
            "",
            "### Авіакомпанії за попитом",
            "",
            markdown_table(tables.get("demand_by_airline", pd.DataFrame()), max_rows=15),
            "",
            "## Пошукова поведінка",
            "",
            "### День пошуку",
            "",
            markdown_table(tables.get("demand_by_search_dow", pd.DataFrame()), max_rows=10),
            "",
            "### Місяць пошуку",
            "",
            markdown_table(tables.get("demand_by_search_month", pd.DataFrame()), max_rows=14),
            "",
            "## Кореляції",
            "",
            markdown_table(tables.get("correlation_matrix", pd.DataFrame()), max_rows=20),
            "",
            "## Статистичні тести",
            "",
            markdown_table(tables.get("statistical_tests", pd.DataFrame()), max_rows=20),
            "",
            "## Модель факторів ціни",
            "",
        ]
    )

    if model_skipped:
        lines.append("_Модель пропущена через параметр `--skip-model`._")
    else:
        lines.extend(
            [
                markdown_table(tables.get("model_metrics", pd.DataFrame()), max_rows=20),
                "",
                "### Feature importance",
                "",
                markdown_table(tables.get("model_feature_importance", pd.DataFrame()), max_rows=20),
            ]
        )

    lines.extend(["", "## Вихідні файли", ""])
    table_names = sorted(tables.keys())
    lines.extend([f"- `tables/{name}.csv`" for name in table_names])
    if chart_paths:
        lines.append("")
        lines.append("## Графіки")
        lines.append("")
        for path in chart_paths:
            lines.append(f"- `charts/{path.name}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detailed EDA/reporting script for flight ticket feature CSVs.",
    )
    parser.add_argument(
        "--input",
        default="etl/exports/flights_features_all.csv",
        help="Path to the flight features CSV.",
    )
    parser.add_argument(
        "--output",
        default="backend/ml/reports/flight_analysis",
        help="Directory where report, tables, and charts will be written.",
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Read only the first N rows. Useful for a fast smoke test.",
    )
    parser.add_argument(
        "--model-sample-size",
        type=int,
        default=50_000,
        help="Maximum rows used for the price model.",
    )
    parser.add_argument(
        "--plot-sample-size",
        type=int,
        default=50_000,
        help="Maximum rows used for scatter plots.",
    )
    parser.add_argument(
        "--stats-sample-size",
        type=int,
        default=200_000,
        help="Maximum rows used for statistical tests.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for sampling and model split.",
    )
    parser.add_argument(
        "--model-n-jobs",
        type=int,
        default=1,
        help="Parallel workers for the Random Forest model. Keep 1 for sandboxed Windows runs.",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip Random Forest price model.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip PNG chart generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = ensure_dir(Path(args.output))
    tables_dir = ensure_dir(output_dir / "tables")
    charts_dir = ensure_dir(output_dir / "charts")

    raw = read_dataset(input_path, args.limit_rows)
    normalized = normalize_dataset(raw)
    enriched = add_derived_features(normalized)
    valid_mask = build_valid_mask(enriched)
    valid = enriched.loc[valid_mask].copy()
    log(f"valid rows: {len(valid):,}; rejected rows: {(~valid_mask).sum():,}")

    tables = build_analysis_tables(enriched, valid, tables_dir)

    stats_table = statistical_tests(valid, args.stats_sample_size, args.random_state)
    add_table(tables, tables_dir, "statistical_tests", stats_table)

    model_skipped = bool(args.skip_model)
    if not args.skip_model:
        log("training price factor model")
        model_metrics, model_importance, model_detail = run_price_model(
            valid,
            sample_size=args.model_sample_size,
            random_state=args.random_state,
            n_jobs=args.model_n_jobs,
        )
        add_table(tables, tables_dir, "model_metrics", model_metrics)
        add_table(tables, tables_dir, "model_feature_importance", model_importance)
        add_table(tables, tables_dir, "model_feature_importance_detail", model_detail)
    else:
        log("model skipped")

    chart_paths: list[Path] = []
    if not args.no_plots:
        log("building charts")
        chart_paths = build_charts(
            valid,
            charts_dir,
            tables,
            sample_size=args.plot_sample_size,
            random_state=args.random_state,
        )
    else:
        log("plots skipped")

    report_path = write_report(output_dir, input_path, tables, chart_paths, model_skipped)
    log(f"report written: {report_path}")
    print(report_path)


if __name__ == "__main__":
    main()
