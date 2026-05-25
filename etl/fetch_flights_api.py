import argparse
import csv
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter

AIRPORTS = [
    # Poland
    {"iata": "KRK", "name": "Krakow John Paul II International Airport", "city": "Krakow", "country": "PL", "lat": 50.077702, "lon": 19.7848},
    {"iata": "WMI", "name": "Warsaw Modlin Airport", "city": "Warsaw", "country": "PL", "lat": 52.451099, "lon": 20.6518},
    {"iata": "WAW", "name": "Warsaw Chopin Airport", "city": "Warsaw", "country": "PL", "lat": 52.165699, "lon": 20.9671},
    {"iata": "KTW", "name": "Katowice Wojciech Korfanty International Airport", "city": "Katowice", "country": "PL", "lat": 50.476015, "lon": 19.080705},
    # France
    {"iata": "CDG", "name": "Charles de Gaulle International Airport", "city": "Paris", "country": "FR", "lat": 49.00896, "lon": 2.554117},
    {"iata": "ORY", "name": "Paris Orly Airport", "city": "Paris", "country": "FR", "lat": 48.72333, "lon": 2.37944},
    {"iata": "MRS", "name": "Marseille Provence Airport", "city": "Marseille", "country": "FR", "lat": 43.438088, "lon": 5.2125},
    {"iata": "NCE", "name": "Nice Cote d Azur Airport", "city": "Nice", "country": "FR", "lat": 43.658401, "lon": 7.21587},
    # United Kingdom
    {"iata": "LHR", "name": "London Heathrow Airport", "city": "London", "country": "GB", "lat": 51.470748, "lon": -0.459909},
    {"iata": "LGW", "name": "London Gatwick Airport", "city": "London", "country": "GB", "lat": 51.148744, "lon": -0.185739},
    {"iata": "MAN", "name": "Manchester Airport", "city": "Manchester", "country": "GB", "lat": 53.349375, "lon": -2.279521},
    # Spain
    {"iata": "MAD", "name": "Adolfo Suarez Madrid Barajas Airport", "city": "Madrid", "country": "ES", "lat": 40.493407, "lon": -3.572249},
    {"iata": "BCN", "name": "Josep Tarradellas Barcelona El Prat Airport", "city": "Barcelona", "country": "ES", "lat": 41.2971, "lon": 2.07846},
    # Italy
    {"iata": "FCO", "name": "Rome Fiumicino Leonardo da Vinci International Airport", "city": "Rome", "country": "IT", "lat": 41.804532, "lon": 12.251998},
    {"iata": "MXP", "name": "Milan Malpensa International Airport", "city": "Milan", "country": "IT", "lat": 45.6306, "lon": 8.72811},
    {"iata": "VCE", "name": "Venice Marco Polo Airport", "city": "Venice", "country": "IT", "lat": 45.505299, "lon": 12.3519},
]


def parse_price(value):
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    if not isinstance(value, str):
        return None, None

    s = value.strip().replace("\u00a0", " ")

    m = re.search(r"\b([A-Za-z]{3})\b\s*([0-9][0-9\s,\.]*)", s)
    if m:
        cur = m.group(1).upper()
        num = re.sub(r"[^\d.]", "", m.group(2).replace(",", "."))
        return (float(num), cur) if num else (None, cur)

    m = re.search(r"([0-9][0-9\s,\.]*)\s*\b([A-Za-z]{3})\b", s)
    if m:
        cur = m.group(2).upper()
        num = re.sub(r"[^\d.]", "", m.group(1).replace(",", "."))
        return (float(num), cur) if num else (None, cur)

    num = re.sub(r"[^\d.]", "", s.replace(",", "."))
    return (float(num), None) if num else (None, None)


def _normalize_text_value(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def _normalize_numeric_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 2)
    return value


def get_flights_data(
    trip_type,
    depart_date,
    from_iata,
    to_iata,
    return_date=None,
    seat="economy",
    adults=1,
    currency="USD",
):
    if trip_type == "one-way":
        flight_segments = [
            FlightData(
                date=depart_date,
                from_airport=from_iata,
                to_airport=to_iata,
            )
        ]
    elif trip_type == "round-trip":
        if not return_date:
            raise ValueError("return_date is required for round-trip")
        flight_segments = [
            FlightData(
                date=depart_date,
                from_airport=from_iata,
                to_airport=to_iata,
            ),
            FlightData(
                date=return_date,
                from_airport=to_iata,
                to_airport=from_iata,
            ),
        ]
    else:
        raise ValueError("trip_type must be 'one-way' or 'round-trip'")

    flt = create_filter(
        flight_data=flight_segments,
        trip=trip_type,
        seat=seat,
        passengers=Passengers(adults=adults),
    )

    result = get_flights_from_filter(flt, currency=currency)

    flights_output = []
    seen_offers = set()
    fallback_depart_date = date.fromisoformat(depart_date)
    for fl in getattr(result, "flights", []) or []:
        price_value, price_currency = parse_price(getattr(fl, "price", None))
        airline = (
            getattr(fl, "name", None)
            or getattr(fl, "airline", None)
            or getattr(fl, "airline_name", None)
            or getattr(fl, "carrier", None)
            or getattr(fl, "carrier_name", None)
        )
        offer = {
            "trip_type": trip_type,
            "departure": getattr(fl, "departure", None),
            "arrival": getattr(fl, "arrival", None),
            "duration": getattr(fl, "duration", None),
            "stops": getattr(fl, "stops", None),
            "airline": airline,
            "price_value": price_value,
            "currency": price_currency,
            "raw_price": getattr(fl, "price", None),
        }
        signature = _flight_offer_signature(offer, fallback_date=fallback_depart_date)
        if signature in seen_offers:
            continue
        seen_offers.add(signature)
        flights_output.append(offer)

    return flights_output


def get_airports_by_country(country_codes):
    codes = {c.upper() for c in country_codes}
    return [a for a in AIRPORTS if a.get("country") in codes]


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _extract_from_mapping(mapping, keys):
    for k in keys:
        if k in mapping and mapping[k] is not None:
            return mapping[k]
    return None


def _extract_from_object(obj, attr_names):
    for name in attr_names:
        if hasattr(obj, name):
            v = getattr(obj, name)
            if v is not None:
                return v
    return None


def parse_datetime_like(value, fallback_date=None, pick="first"):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, dict):
        inner = _extract_from_mapping(
            value,
            ["datetime", "date_time", "local_datetime", "time", "local_time", "departure", "arrival"],
        )
        if inner is not None:
            return parse_datetime_like(inner, fallback_date=fallback_date, pick=pick)
        return None

    if not isinstance(value, str):
        inner = _extract_from_object(
            value,
            ["datetime", "date_time", "local_datetime", "time", "local_time", "departure", "arrival"],
        )
        if inner is not None:
            return parse_datetime_like(inner, fallback_date=fallback_date, pick=pick)
        return None

    s = value.strip()

    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", s)
    if m:
        return datetime(
            int(m.group(1)[0:4]),
            int(m.group(1)[5:7]),
            int(m.group(1)[8:10]),
            int(m.group(2)),
            int(m.group(3)),
        )

    m = re.search(r"\b(\d{1,2}):(\d{2})\s*([AP]M)\s*on\s*(\w{3}),\s*(\w{3})\s*(\d{1,2})\b", s)
    if m:
        year = fallback_date.year if fallback_date else datetime.today().year
        dt_str = f"{year} {m.group(4)} {m.group(5)} {int(m.group(6)):02d} {m.group(1)}:{m.group(2)} {m.group(3)}"
        try:
            return datetime.strptime(dt_str, "%Y %a %b %d %I:%M %p")
        except Exception:
            pass

    m = re.search(r"\b(\d{1,2}):(\d{2})\s*([AP]M)\b", s)
    if m and fallback_date:
        hour = int(m.group(1)) % 12
        if m.group(3) == "PM":
            hour += 12
        return datetime(
            fallback_date.year,
            fallback_date.month,
            fallback_date.day,
            hour,
            int(m.group(2)),
        )

    times = re.findall(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", s)
    if times and fallback_date:
        hh, mm = times[0] if pick == "first" else times[-1]
        return datetime(
            fallback_date.year,
            fallback_date.month,
            fallback_date.day,
            int(hh),
            int(mm),
        )

    return None


def parse_duration_to_minutes(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None

    s = value.strip().lower()
    hours = 0
    minutes = 0

    m = re.search(r"(\d+)\s*h(?:r|rs|our|ours)?", s)
    if m:
        hours = int(m.group(1))

    m = re.search(r"(\d+)\s*m(?:in|ins|inute|inutes)?", s)
    if m:
        minutes = int(m.group(1))

    if hours or minutes:
        return hours * 60 + minutes

    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    return None


def daypart(hour):
    if hour is None:
        return None
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Night"


def season_of_month(month):
    if month in (12, 1, 2):
        return 0
    if month in (3, 4, 5):
        return 1
    if month in (6, 7, 8):
        return 2
    return 3


def normalize_trip_type(trip_type):
    if trip_type == "one-way":
        return "One_way"
    if trip_type == "round-trip":
        return "Round_trip"
    return trip_type


def normalize_travel_class(seat):
    mapping = {
        "economy": "Economy",
        "business": "Business",
        "first": "First",
        "premium-economy": "Premium economy",
    }
    return mapping.get(seat, seat)


def normalize_airline(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return "; ".join([str(v) for v in value if v is not None])
    return str(value)


def normalize_stops(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (list, tuple)):
        return max(len(value) - 1, 0)
    return None


def _flight_offer_signature(flight, fallback_date):
    dep_dt = parse_datetime_like(flight.get("departure"), fallback_date=fallback_date, pick="first")
    arr_dt = parse_datetime_like(flight.get("arrival"), fallback_date=fallback_date, pick="last")
    duration_minutes = parse_duration_to_minutes(flight.get("duration"))

    return (
        _normalize_text_value(flight.get("trip_type")),
        dep_dt.isoformat(timespec="minutes") if dep_dt else _normalize_text_value(flight.get("departure")),
        arr_dt.isoformat(timespec="minutes") if arr_dt else _normalize_text_value(flight.get("arrival")),
        duration_minutes,
        normalize_stops(flight.get("stops")),
        _normalize_text_value(normalize_airline(flight.get("airline"))),
        _normalize_numeric_value(flight.get("price_value")),
        _normalize_text_value(flight.get("currency")),
    )


def _row_signature(row):
    return tuple(_normalize_numeric_value(row.get(field)) for field in CSV_FIELDS)


def _dedupe_rows(rows):
    seen = set()
    deduped = []
    for row in rows:
        signature = _row_signature(row)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped


def build_rows_for_request(
    depart_date,
    origin,
    dest,
    trip_type,
    seat,
    currency,
    search_date,
    write_empty_rows=True,
    sleep_sec=0,
):
    depart_dt = date.fromisoformat(depart_date)
    days_to_departure = (depart_dt - search_date).days

    distance_km = haversine_km(
        origin.get("lat"),
        origin.get("lon"),
        dest.get("lat"),
        dest.get("lon"),
    )
    origin_type = origin.get("type", "large_airport")
    destination_type = dest.get("type", "large_airport")

    try:
        flights = get_flights_data(
            trip_type=trip_type,
            depart_date=depart_date,
            from_iata=origin["iata"],
            to_iata=dest["iata"],
            seat=seat,
            adults=1,
            currency=currency,
        )
    except Exception as exc:
        return None, str(exc)

    if sleep_sec:
        time.sleep(sleep_sec)

    rows = []
    if not flights and write_empty_rows:
        rows.append(
            {
                "days_to_departure": days_to_departure,
                "search_date": search_date.isoformat(),
                "departure_date": depart_dt.isoformat(),
                "origin": origin["iata"],
                "destination": dest["iata"],
                "distance_km": distance_km,
                "origin_type": origin_type,
                "destination_type": destination_type,
                "airline": None,
                "travel_class": normalize_travel_class(seat),
                "passengers_total": 1,
                "trip_type": normalize_trip_type(trip_type),
                "stops": None,
                "duration_minutes": None,
                "price": None,
                "depart_hour": None,
                "departure_time": None,
                "arrival_time": None,
                "depart_dow": depart_dt.weekday(),
                "depart_month": depart_dt.month,
                "depart_is_weekend": 1 if depart_dt.weekday() >= 5 else 0,
                "depart_season": season_of_month(depart_dt.month),
                "is_holiday_depart": 0,
                "search_dow": search_date.weekday(),
                "search_month": search_date.month,
                "search_is_weekend": 1 if search_date.weekday() >= 5 else 0,
                "search_season": season_of_month(search_date.month),
            }
        )
        return rows, None

    for fl in flights:
        dep_dt = parse_datetime_like(fl.get("departure"), fallback_date=depart_dt, pick="first")
        arr_dt = parse_datetime_like(fl.get("arrival"), fallback_date=depart_dt, pick="last")

        depart_hour = dep_dt.hour if dep_dt else None
        departure_time = daypart(depart_hour)
        arrival_time = daypart(arr_dt.hour) if arr_dt else None

        duration_minutes = parse_duration_to_minutes(fl.get("duration"))
        if duration_minutes is None and dep_dt and arr_dt:
            delta = arr_dt - dep_dt
            minutes = int(delta.total_seconds() / 60)
            if minutes < 0:
                minutes += 24 * 60
            duration_minutes = minutes

        rows.append(
            {
                "days_to_departure": days_to_departure,
                "search_date": search_date.isoformat(),
                "departure_date": depart_dt.isoformat(),
                "origin": origin["iata"],
                "destination": dest["iata"],
                "distance_km": distance_km,
                "origin_type": origin_type,
                "destination_type": destination_type,
                "airline": normalize_airline(fl.get("airline")),
                "travel_class": normalize_travel_class(seat),
                "passengers_total": 1,
                "trip_type": normalize_trip_type(trip_type),
                "stops": normalize_stops(fl.get("stops")),
                "duration_minutes": duration_minutes,
                "price": fl.get("price_value"),
                "depart_hour": depart_hour,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "depart_dow": depart_dt.weekday(),
                "depart_month": depart_dt.month,
                "depart_is_weekend": 1 if depart_dt.weekday() >= 5 else 0,
                "depart_season": season_of_month(depart_dt.month),
                "is_holiday_depart": 0,
                "search_dow": search_date.weekday(),
                "search_month": search_date.month,
                "search_is_weekend": 1 if search_date.weekday() >= 5 else 0,
                "search_season": season_of_month(search_date.month),
            }
        )

    return _dedupe_rows(rows), None


def iter_dates(start_date, days):
    for i in range(days):
        yield (start_date + timedelta(days=i)).isoformat()


CSV_FIELDS = [
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


def export_flights_for_days_csv(
    out_csv_path,
    origin_countries=("PL", "GB"),
    destination_countries=("FR", "ES", "IT"),
    trip_type="one-way",
    seats=("economy", "business", "first", "premium-economy"),
    currency="USD",
    days=30,
    start_date_value=None,
    search_date_value=None,
    sleep_sec=0,
    max_workers=8,
    write_empty_rows=True,
    error_csv_path=None,
):
    start_ts = time.perf_counter()
    origin_airports = get_airports_by_country(origin_countries)
    destination_airports = get_airports_by_country(destination_countries)

    start_date_val = start_date_value or date.today()
    search_date_val = search_date_value or start_date_val
    errors = []
    total_rows = 0
    total_empty = 0

    requests = []
    for depart_date in iter_dates(start_date_val, days):
        for origin in origin_airports:
            for dest in destination_airports:
                if dest["iata"] == origin["iata"]:
                    continue
                requests.append((depart_date, origin, dest))

    err_file = None
    err_writer = None
    if error_csv_path:
        err_file = open(error_csv_path, "w", newline="", encoding="utf-8")
        err_writer = csv.DictWriter(
            err_file,
            fieldnames=["from_iata", "to_iata", "depart_date", "seat", "error"],
        )
        err_writer.writeheader()

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    build_rows_for_request,
                    depart_date,
                    origin,
                    dest,
                    trip_type,
                    seat,
                    currency,
                    search_date_val,
                    write_empty_rows,
                    sleep_sec,
                ): (depart_date, origin, dest, seat)
                for depart_date, origin, dest in requests
                for seat in seats
            }

            for future in as_completed(future_map):
                depart_date, origin, dest, seat = future_map[future]
                rows, err = future.result()
                if err:
                    error_row = {
                        "from_iata": origin["iata"],
                        "to_iata": dest["iata"],
                        "depart_date": depart_date,
                        "seat": seat,
                        "error": err,
                    }
                    errors.append(error_row)
                    if err_writer:
                        err_writer.writerow(error_row)
                    continue

                if rows:
                    for row in rows:
                        writer.writerow(row)
                    total_rows += len(rows)
                    if len(rows) == 1 and rows[0].get("price") is None and rows[0].get("airline") is None:
                        total_empty += 1

    if err_file:
        err_file.close()

    elapsed_sec = time.perf_counter() - start_ts
    summary = {
        "requests": len(requests) * len(seats),
        "rows_written": total_rows,
        "empty_combinations": total_empty,
        "elapsed_sec": elapsed_sec,
    }
    return summary, errors


def _parse_list(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(description="Fetch flights via API and export CSV.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--error-output", default=None, help="CSV path for errors.")
    parser.add_argument("--days", type=int, default=30, help="Number of departure days to fetch.")
    parser.add_argument("--start-date", default=date.today().isoformat(), help="Start date (YYYY-MM-DD).")
    parser.add_argument("--search-date", default=None, help="Search date (YYYY-MM-DD). Defaults to start-date.")
    parser.add_argument("--origin-countries", default="PL,GB", help="Comma-separated origin country codes.")
    parser.add_argument("--destination-countries", default="FR,ES,IT", help="Comma-separated destination country codes.")
    parser.add_argument("--trip-type", default="one-way", help="Trip type: one-way or round-trip.")
    parser.add_argument("--seats", default="economy,business,first,premium-economy", help="Comma-separated seat classes.")
    parser.add_argument("--currency", default="USD", help="Currency for prices.")
    parser.add_argument("--sleep-sec", type=float, default=0, help="Sleep between requests (seconds).")
    parser.add_argument("--max-workers", type=int, default=8, help="ThreadPool workers.")
    parser.add_argument("--no-empty-rows", dest="write_empty_rows", action="store_false", help="Do not write empty rows.")
    parser.set_defaults(write_empty_rows=True)
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    err_path = Path(args.error_output) if args.error_output else None
    if err_path:
        err_path.parent.mkdir(parents=True, exist_ok=True)

    start_date_val = date.fromisoformat(args.start_date)
    search_date_val = date.fromisoformat(args.search_date) if args.search_date else start_date_val

    summary, errors = export_flights_for_days_csv(
        out_csv_path=str(out_path),
        origin_countries=tuple(_parse_list(args.origin_countries)),
        destination_countries=tuple(_parse_list(args.destination_countries)),
        trip_type=args.trip_type,
        seats=tuple(_parse_list(args.seats)),
        currency=args.currency,
        days=args.days,
        start_date_value=start_date_val,
        search_date_value=search_date_val,
        sleep_sec=args.sleep_sec,
        max_workers=args.max_workers,
        write_empty_rows=args.write_empty_rows,
        error_csv_path=str(err_path) if err_path else None,
    )

    print(f"saved: {out_path}")
    print(f"requests: {summary['requests']}")
    print(f"rows_written: {summary['rows_written']}")
    print(f"empty_combinations: {summary['empty_combinations']}")
    print(f"elapsed_sec: {summary['elapsed_sec']:.2f}")
    print(f"errors: {len(errors)}")


if __name__ == "__main__":
    main()
