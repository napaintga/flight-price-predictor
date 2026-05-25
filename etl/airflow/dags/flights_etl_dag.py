from __future__ import annotations

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT_ENV = os.getenv("PROJECT_ROOT")
REPO_ROOT = Path(PROJECT_ROOT_ENV).resolve() if PROJECT_ROOT_ENV else Path(__file__).resolve().parents[3]
ETL_DIR = REPO_ROOT / "etl"
EXPORTS_DIR = ETL_DIR / "exports"
DAILY_DIR = EXPORTS_DIR / "daily"


def _param(context, key, default):
    params = context.get("params") or {}
    value = params.get(key)
    if value not in (None, ""):
        return value
    env_value = os.getenv(f"FLIGHTS_{key.upper()}")
    if env_value not in (None, ""):
        return env_value
    return default


def _run_fetch(**context):
    run_date = context["logical_date"].date()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = DAILY_DIR / f"flight_{run_date.isoformat()}.csv"
    err_csv = DAILY_DIR / f"errors_{run_date.isoformat()}.csv"

    origin_countries = _param(context, "origin_countries", "PL,GB")
    destination_countries = _param(context, "destination_countries", "FR,ES,IT")
    seats = _param(context, "seats", "economy,business,first,premium-economy")
    trip_type = _param(context, "trip_type", "one-way")
    currency = _param(context, "currency", "USD")
    days = str(_param(context, "days", "30"))
    max_workers = str(_param(context, "max_workers", "8"))
    sleep_sec = str(_param(context, "sleep_sec", "0"))

    cmd = [
        sys.executable,
        str(ETL_DIR / "fetch_flights_api.py"),
        "--output",
        str(out_csv),
        "--error-output",
        str(err_csv),
        "--days",
        days,
        "--start-date",
        run_date.isoformat(),
        "--search-date",
        run_date.isoformat(),
        "--origin-countries",
        origin_countries,
        "--destination-countries",
        destination_countries,
        "--seats",
        seats,
        "--trip-type",
        trip_type,
        "--currency",
        currency,
        "--max-workers",
        max_workers,
        "--sleep-sec",
        sleep_sec,
    ]
    subprocess.run(cmd, check=True)


def _run_build_old():
    cmd = [
        sys.executable,
        str(ETL_DIR / "build_old_flights_features.py"),
        "--output",
        str(EXPORTS_DIR / "flights_features.csv"),
    ]
    subprocess.run(cmd, check=True)


def _run_prepare_daily():
    cmd = [
        sys.executable,
        str(ETL_DIR / "deduplicate_daily_files.py"),
        "--daily-dir",
        str(DAILY_DIR),
        "--mode",
        "flight_id",
        "--keep",
        "last",
    ]
    subprocess.run(cmd, check=True)


def _run_merge():
    cmd = [
        sys.executable,
        str(ETL_DIR / "merge_flights_features.py"),
        "--daily-dir",
        str(DAILY_DIR),
        "--old-features",
        str(EXPORTS_DIR / "flights_features.csv"),
        "--output",
        str(EXPORTS_DIR / "flights_features_all.csv"),
    ]
    subprocess.run(cmd, check=True)


with DAG(
    dag_id="flights_etl_daily",
    start_date=pendulum.datetime(2026, 2, 23, tz="UTC"),
    schedule="@daily",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=10)},
    params={
        "origin_countries": "PL,GB",
        "destination_countries": "FR,ES,IT",
        "seats": "economy,business,first,premium-economy",
        "trip_type": "one-way",
        "currency": "USD",
        "days": "1",
        "max_workers": "8",
        "sleep_sec": "0",
    },
    tags=["etl", "flights"],
) as dag:
    fetch_api_flights = PythonOperator(
        task_id="fetch_api_flights",
        python_callable=_run_fetch,
    )

    build_old_features = PythonOperator(
        task_id="build_old_features",
        python_callable=_run_build_old,
    )

    prepare_daily_files = PythonOperator(
        task_id="prepare_daily_files",
        python_callable=_run_prepare_daily,
    )

    merge_and_clean = PythonOperator(
        task_id="merge_and_clean",
        python_callable=_run_merge,
    )

    fetch_api_flights >> prepare_daily_files
    [prepare_daily_files, build_old_features] >> merge_and_clean
