from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from add_flight_id_to_daily import _build_flight_id_values


def _load_env(repo_root: Path) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    candidates = [
        repo_root / ".env",
        repo_root / "backend" / ".env",
        repo_root / "backend" / ".env.local",
    ]
    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)


def _require_db_url(db_url: str | None) -> str:
    if not db_url:
        raise ValueError("DATABASE_URL is not set. Provide --database-url or set env DATABASE_URL.")
    return db_url


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _redact_db_url(db_url: str) -> str:
    try:
        parts = urlsplit(db_url)
        if parts.password is None:
            return db_url
        netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return db_url


def _load_airports(repo_root: Path) -> dict[str, dict[str, Any]]:
    airports_path = repo_root / "etl" / "airflow" / "world-airports.csv"
    if not airports_path.exists():
        _log("airports: world-airports.csv not found, continuing without airport metadata")
        return {}
    with airports_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        result: dict[str, dict[str, Any]] = {}
        for row in reader:
            code = (row.get("iata_code") or "").strip()
            if not code:
                continue
            if code in result:
                continue
            result[code] = row
        return result


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _season_from_month(month: int | None) -> int | None:
    if not month:
        return None
    if month in (12, 1, 2):
        return 0
    if month in (3, 4, 5):
        return 1
    if month in (6, 7, 8):
        return 2
    return 3


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("amount", "value", "price"):
            if key in value:
                return _parse_price(value.get(key))
        return None
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.]", "", value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lookup_airport(airports: dict[str, dict[str, Any]], code: str | None) -> dict[str, Any] | None:
    if not code:
        return None
    return airports.get(code)


def _time_bucket_from_hour(hour: int | None) -> str | None:
    if hour is None:
        return None
    if 0 <= hour < 4:
        return "Late_Night"
    if 4 <= hour < 8:
        return "Early_Morning"
    if 8 <= hour < 12:
        return "Morning"
    if 12 <= hour < 16:
        return "Afternoon"
    if 16 <= hour < 20:
        return "Evening"
    return "Night"


def _travel_class_label(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    mapping = {1: "Economy", 2: "Premium economy", 3: "Business", 4: "First"}
    try:
        return mapping.get(int(value))
    except (TypeError, ValueError):
        return None


def _trip_type_label(type_value: Any, return_date: Any) -> str | None:
    try:
        t = int(type_value)
    except (TypeError, ValueError):
        t = None
    if t == 1:
        return "Round_trip"
    if t == 2:
        return "One_way"
    if t == 3:
        return "Multi_city"
    if return_date:
        return "Round_trip"
    return "One_way"


def _primary_airline(entry: dict[str, Any]) -> str | None:
    airline = entry.get("airline")
    if airline:
        return airline
    segments = entry.get("flights") or []
    if segments:
        return segments[0].get("airline")
    return None


def _duration_minutes(entry: dict[str, Any]) -> int | None:
    total = entry.get("total_duration")
    if isinstance(total, int):
        return total
    segments = entry.get("flights") or []
    if not segments:
        return None
    total = 0
    for seg in segments:
        try:
            total += int(seg.get("duration") or 0)
        except (TypeError, ValueError):
            continue
    return total or None


def _departure_datetime(entry: dict[str, Any]) -> datetime | None:
    segments = entry.get("flights") or []
    if not segments:
        return None
    dep = (segments[0].get("departure_airport") or {}).get("time")
    return _parse_dt(dep)


def _arrival_datetime(entry: dict[str, Any]) -> datetime | None:
    segments = entry.get("flights") or []
    if not segments:
        return None
    arr = (segments[-1].get("arrival_airport") or {}).get("time")
    return _parse_dt(arr)


def _departure_iata(entry: dict[str, Any], search_params: dict[str, Any]) -> str | None:
    segments = entry.get("flights") or []
    if segments:
        return (segments[0].get("departure_airport") or {}).get("id")
    return search_params.get("departure_id")


def _arrival_iata(entry: dict[str, Any], search_params: dict[str, Any]) -> str | None:
    segments = entry.get("flights") or []
    if segments:
        return (segments[-1].get("arrival_airport") or {}).get("id")
    return search_params.get("arrival_id")


def _stops(entry: dict[str, Any]) -> int | None:
    segments = entry.get("flights") or []
    if not segments:
        return None
    return max(len(segments) - 1, 0)


def _holiday_checker():
    try:
        import holidays  # type: ignore
    except Exception:
        return None
    return holidays


def _is_holiday_within_week(
    holidays_lib: Any,
    country_code: str | None,
    start_date: date | None,
    cache: dict[tuple[str, int], Any],
) -> int | None:
    if not holidays_lib or not country_code or not start_date:
        return None
    days_to_check = [start_date + timedelta(days=offset) for offset in range(0, 7)]
    years = sorted({d.year for d in days_to_check})
    calendars = []
    for year in years:
        key = (country_code, year)
        if key not in cache:
            try:
                cache[key] = holidays_lib.country_holidays(country_code, years=[year])
            except Exception:
                cache[key] = None
        cal = cache.get(key)
        if cal:
            calendars.append(cal)
    if not calendars:
        return None
    for d in days_to_check:
        for cal in calendars:
            if d in cal:
                return 1
    return 0


def _passengers_total(search_params: dict[str, Any]) -> int:
    for key in ("passengers", "passengers_count", "passenger_count"):
        value = search_params.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, dict):
            try:
                return int(value.get("total"))
            except (TypeError, ValueError):
                pass
    total = 0
    for key in ("adults", "children", "infants", "infants_in_seat", "infants_on_lap"):
        try:
            total += int(search_params.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return total if total > 0 else 1


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s);", (table_name,))
        return cur.fetchone()[0] is not None


def _iter_snapshots(conn) -> Iterable[dict[str, Any]]:
    rows = []
    if _table_exists(conn, "public.serpapi_search_snapshots_log"):
        _log("db: using table public.serpapi_search_snapshots_log")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT response, fetched_at
                FROM serpapi_search_snapshots_log
                ORDER BY fetched_at ASC
                """
            )
            rows = cur.fetchall()
        _log(f"db: snapshots_log rows={len(rows)}")
    else:
        _log("db: table public.serpapi_search_snapshots_log not found")
    if rows:
        return rows
    if not _table_exists(conn, "public.serpapi_search_snapshots"):
        _log("db: table public.serpapi_search_snapshots not found")
        return []
    _log("db: using table public.serpapi_search_snapshots")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT response, fetched_at
            FROM serpapi_search_snapshots
            ORDER BY fetched_at ASC
            """
        )
        rows = cur.fetchall()
    _log(f"db: snapshots rows={len(rows)}")
    return rows


def _row_for_entry(
    *,
    entry: dict[str, Any],
    search_params: dict[str, Any],
    search_date: date,
    airports: dict[str, dict[str, Any]],
    holidays_lib: Any,
    holiday_cache: dict[tuple[str, int], Any],
) -> dict[str, Any] | None:
    depart_dt = _departure_datetime(entry)
    depart_date = _parse_date(depart_dt) or _parse_date(search_params.get("outbound_date"))
    if not depart_date:
        return None

    origin = _departure_iata(entry, search_params)
    destination = _arrival_iata(entry, search_params)

    origin_info = _lookup_airport(airports, origin)
    dest_info = _lookup_airport(airports, destination)

    origin_type = origin_info.get("type") if origin_info else None
    dest_type = dest_info.get("type") if dest_info else None

    distance_km = None
    if origin_info and dest_info:
        try:
            lat1 = float(origin_info.get("latitude_deg") or 0)
            lon1 = float(origin_info.get("longitude_deg") or 0)
            lat2 = float(dest_info.get("latitude_deg") or 0)
            lon2 = float(dest_info.get("longitude_deg") or 0)
            if lat1 and lon1 and lat2 and lon2:
                distance_km = _haversine_km(lat1, lon1, lat2, lon2)
        except (TypeError, ValueError):
            distance_km = None

    search_dow = search_date.weekday()
    search_month = search_date.month
    search_is_weekend = 1 if search_dow >= 5 else 0
    search_season = _season_from_month(search_month)

    depart_dow = depart_date.weekday()
    depart_month = depart_date.month
    depart_is_weekend = 1 if depart_dow >= 5 else 0
    depart_season = _season_from_month(depart_month)

    holiday_depart = _is_holiday_within_week(
        holidays_lib,
        (dest_info or {}).get("iso_country"),
        depart_date,
        holiday_cache,
    )

    depart_hour = depart_dt.hour if depart_dt else None
    depart_bucket = _time_bucket_from_hour(depart_hour)
    arrival_dt = _arrival_datetime(entry)
    arrival_bucket = _time_bucket_from_hour(arrival_dt.hour if arrival_dt else None)
    price = _parse_price(entry.get("price"))
    passengers_total = _passengers_total(search_params)

    return {
        "days_to_departure": (depart_date - search_date).days,
        "search_date": search_date.isoformat(),
        "departure_date": depart_date.isoformat(),
        "origin": origin,
        "destination": destination,
        "distance_km": distance_km,
        "origin_type": origin_type,
        "destination_type": dest_type,
        "airline": _primary_airline(entry),
        "travel_class": _travel_class_label(
            (entry.get("flights") or [{}])[0].get("travel_class")
            or entry.get("travel_class")
            or search_params.get("travel_class")
        ),
        "passengers_total": passengers_total,
        "trip_type": _trip_type_label(
            search_params.get("type"),
            search_params.get("return_date"),
        ),
        "stops": _stops(entry),
        "duration_minutes": _duration_minutes(entry),
        "price": price,
        "depart_hour": depart_hour,
        "departure_time": depart_bucket,
        "arrival_time": arrival_bucket,
        "depart_dow": depart_dow,
        "depart_month": depart_month,
        "depart_is_weekend": depart_is_weekend,
        "depart_season": depart_season,
        "is_holiday_depart": holiday_depart,
        "search_dow": search_dow,
        "search_month": search_month,
        "search_is_weekend": search_is_weekend,
        "search_season": search_season,
    }


def _default_output_path(repo_root: Path) -> Path:
    out_dir = repo_root / "etl" / "exports"
    return out_dir / "flights_features.csv"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build features table from historical SerpApi snapshots."
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection URL. Falls back to env DATABASE_URL.",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="Output CSV path. Defaults to etl/exports/flights_features.csv",
        default=None,
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _load_env(repo_root)
    db_url = _require_db_url(args.database_url or os.getenv("DATABASE_URL"))
    _log(f"db: connecting to {_redact_db_url(db_url)}")

    airports = _load_airports(repo_root)
    _log(f"airports: loaded {len(airports)} records")
    holidays_lib = _holiday_checker()
    _log(f"holidays: {'enabled' if holidays_lib else 'disabled'}")
    holiday_cache: dict[tuple[str, int], Any] = {}

    dedupe_columns = [
        "days_to_departure",
        "search_date",
        "departure_date",
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
    output_columns = [
        "days_to_departure",
        "search_date",
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

    rows_out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    with psycopg2.connect(db_url) as conn:
        snapshots = _iter_snapshots(conn)
        _log(f"db: total snapshots to process={len(snapshots)}")
        for row in snapshots:
            response = row.get("response") or {}
            fetched_at = row.get("fetched_at")
            if not fetched_at:
                continue
            search_date = _parse_date(fetched_at)
            if not search_date:
                continue
            search_params = response.get("search_parameters") or {}
            entries = (response.get("best_flights") or []) + (
                response.get("other_flights") or []
            )
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                rec = _row_for_entry(
                    entry=entry,
                    search_params=search_params,
                    search_date=search_date,
                    airports=airports,
                    holidays_lib=holidays_lib,
                    holiday_cache=holiday_cache,
                )
                if rec is None:
                    continue
                key = tuple(rec.get(col) for col in dedupe_columns)
                if key in seen:
                    continue
                seen.add(key)
                rows_out.append(rec)

    output_path = Path(args.output) if args.output else _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows_out)
    if frame.empty:
        frame = pd.DataFrame(columns=output_columns)
    else:
        for col in dedupe_columns:
            if col not in frame.columns:
                frame[col] = pd.NA
        frame = frame[dedupe_columns]
        frame["flight_id"] = pd.Series(_build_flight_id_values(frame), dtype="string")
        frame = frame[output_columns]
    frame.to_csv(output_path, index=False)

    _log(f"output: rows_written={len(frame)}")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ETL failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
