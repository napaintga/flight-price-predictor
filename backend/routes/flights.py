from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from core import DATABASE_URL, _build_serpapi_params, _iso_z
from db.ops import _resolve_search_keys
from services.auth import _get_user_from_auth_header
from services.serpapi import (
    _build_price_snapshots,
    _find_flight_signature_in_snapshots,
    _flight_signature_from_flight,
    _flight_signature_route_from_flight,
    _flight_signature_weak_from_flight,
    _map_serpapi_flights,
    _serpapi_request_cached,
)
from services.local_ticket_history import build_local_ticket_history
from services.user_data import _log_search_history

router = APIRouter()


def _find_flight_by_uid_or_signature(
    flights: list[dict[str, Any]],
    flight_uid: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    found = next((f for f in flights if f.get("uid") == flight_uid), None)
    if found:
        return found

    matching_keys = _resolve_search_keys(params)
    signature, signature_weak, signature_route = _find_flight_signature_in_snapshots(
        matching_keys, flight_uid
    )
    if signature:
        found = next(
            (f for f in flights if _flight_signature_from_flight(f) == signature),
            None,
        )
    if found:
        return found
    if signature_weak:
        found = next(
            (
                f
                for f in flights
                if _flight_signature_weak_from_flight(f) == signature_weak
            ),
            None,
        )
    if found:
        return found
    if signature_route:
        found = next(
            (
                f
                for f in flights
                if _flight_signature_route_from_flight(f) == signature_route
            ),
            None,
        )
    return found


def _ticket_from_flight_for_local_history(
    flight: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    first_segment = (flight.get("segments") or [{}])[0]
    last_segment = (flight.get("segments") or [{}])[-1]
    passengers = 0
    for key in ("adults", "children", "infants_in_seat", "infants_on_lap"):
        try:
            passengers += int(params.get(key) or 0)
        except (TypeError, ValueError):
            pass

    return {
        "id": f"snapshot-{flight.get('uid') or flight.get('id')}",
        "flightId": str(flight.get("uid") or flight.get("id") or ""),
        "origin": flight.get("origin") or params.get("departure_id"),
        "destination": flight.get("destination") or params.get("arrival_id"),
        "originName": (first_segment.get("departure_airport") or {}).get("name"),
        "destinationName": (last_segment.get("arrival_airport") or {}).get("name"),
        "airline": flight.get("airline"),
        "departAt": flight.get("departAt") or params.get("outbound_date"),
        "currency": flight.get("currency") or params.get("currency") or "USD",
        "duration": flight.get("duration"),
        "durationMinutes": flight.get("total_duration_minutes"),
        "stops": flight.get("stops"),
        "tripType": params.get("type"),
        "travelClass": params.get("travel_class"),
        "passengers": passengers or None,
        "searchParams": "&".join(
            f"{key}={value}" for key, value in params.items() if value is not None
        ),
        "createdAt": flight.get("asOf"),
    }


def _merge_db_and_local_price_snapshots(
    db_snapshots: list[dict[str, Any]],
    local_history: dict[str, Any] | None,
    currency: str | None,
) -> list[dict[str, Any]]:
    merged = [{**item, "source": item.get("source") or "db"} for item in db_snapshots]
    db_days = {
        str(item.get("asOf") or "")[:10]
        for item in db_snapshots
        if item.get("asOf")
    }
    for point in (local_history or {}).get("actual") or []:
        ts = point.get("ts")
        day = str(point.get("sourceDate") or ts or "")[:10]
        if not ts or day in db_days:
            continue
        merged.append(
            {
                "asOf": ts,
                "price": point.get("price"),
                "currency": currency or (local_history or {}).get("currency"),
                "snapshotId": None,
                "source": "local_csv",
                "sourceFile": point.get("sourceFile"),
                "matchMode": point.get("matchMode"),
            }
        )
    return sorted(merged, key=lambda item: str(item.get("asOf") or ""), reverse=True)


@router.get("/api/flights")
def list_flights(
    # required core:
    departure_id: str = Query(..., description="IATA code(s) like CDG or kgmid like /m/0vzm; you can pass multiple comma-separated."),
    arrival_id: str = Query(..., description="IATA code(s) like AUS or kgmid like /m/0vzm; you can pass multiple comma-separated."),
    outbound_date: str = Query(..., description="YYYY-MM-DD"),
    # trip type:
    type: Optional[int] = Query(None, description="1 round trip, 2 one way, 3 multi-city"),
    return_date: str | None = Query(None, description="YYYY-MM-DD (required if type=1)"),
    # localization:
    gl: str | None = Query(None, description="country code (e.g. us, uk, fr)"),
    hl: str | None = Query(None, description="language code (e.g. en, fr, uk)"),
    currency: str | None = Query(None, description="e.g. USD, EUR, UAH"),
    # passengers:
    adults: int = Query(1, ge=1, le=9),
    children: int | None = Query(None, ge=0, le=9),
    infants_in_seat: int | None = Query(None, ge=0, le=9),
    infants_on_lap: int | None = Query(None, ge=0, le=9),
    # cabin:
    travel_class: int | None = Query(None, description="1 economy, 2 premium economy, 3 business, 4 first", ge=1, le=4),
    # sorting/filters:
    sort_by: int | None = Query(None, description="1 top, 2 price, 3 dep time, 4 arr time, 5 duration, 6 emissions", ge=1, le=6),
    stops: int | None = Query(None, description="0 any, 1 nonstop, 2 1 stop or fewer, 3 2 stops or fewer", ge=0, le=3),
    include_airlines: str | None = Query(None, description="Comma-separated 2-char airline codes or alliance tokens (STAR_ALLIANCE, SKYTEAM, ONEWORLD)"),
    exclude_airlines: str | None = Query(None, description="Comma-separated 2-char airline codes or alliance tokens"),
    bags: int | None = Query(None, ge=0, le=9),
    max_price: str | None = Query(None, description="Max price (integer)"),
    outbound_times: str | None = Query(None, description="e.g. '4,18' or '4,18,3,19'"),
    return_times: str | None = Query(None, description="e.g. '4,18' or '4,18,3,19' (only with type=1)"),
    emissions: int | None = Query(None, description="1 = less emissions only"),
    layover_duration: str | None = Query(None, description="minutes range e.g. '90,330'"),
    exclude_conns: str | None = Query(None, description="exclude connections airports, comma-separated IATA"),
    max_duration: str | None = Query(None, description="max duration minutes (integer)"),
    # advanced:
    show_hidden: bool | None = Query(None),
    exclude_basic: bool | None = Query(None),
    deep_search: bool | None = Query(None),
    # serpapi:
    no_cache: bool | None = Query(None, description="true = force SerpApi to fetch fresh (their cache off)"),
    authorization: str | None = Header(None),
):
    params = _build_serpapi_params(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
        return_date=return_date,
        gl=gl,
        hl=hl,
        currency=currency,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        travel_class=travel_class,
        sort_by=sort_by,
        stops=stops,
        include_airlines=include_airlines,
        exclude_airlines=exclude_airlines,
        bags=bags,
        max_price=max_price,
        outbound_times=outbound_times,
        return_times=return_times,
        emissions=emissions,
        layover_duration=layover_duration,
        exclude_conns=exclude_conns,
        max_duration=max_duration,
        show_hidden=show_hidden,
        exclude_basic=exclude_basic,
        deep_search=deep_search,
        no_cache=no_cache,
    )
    user = _get_user_from_auth_header(authorization)
    if user:
        try:
            _log_search_history(user["id"], params)
        except Exception:
            # Do not block search results if history logging fails.
            pass

    res = _serpapi_request_cached(params)
    meta = {
        "asOf": res["fetched_at"],
        "fromCache": res["from_cache"],
        "searchKey": res["search_key"],
        "snapshotId": res["snapshot_id"],
        "currency": currency,
    }

    flights = _map_serpapi_flights(res["data"], meta)

    return {
        "asOf": meta["asOf"],  # <-- timestamp for prices
        "fromCache": meta["fromCache"],
        "searchKey": meta["searchKey"],
        "snapshotId": meta["snapshotId"],
        "count": len(flights),
        "flights": flights,
    }


@router.get("/api/flights/{flight_uid}")
def flight_details(
    flight_uid: str,
    departure_id: str = Query(...),
    arrival_id: str = Query(...),
    outbound_date: str = Query(...),
    type: Optional[int] = Query(None),
    return_date: str | None = None,
    gl: str | None = None,
    hl: str | None = None,
    currency: str | None = None,
    adults: int = 1,
    children: int | None = None,
    infants_in_seat: int | None = None,
    infants_on_lap: int | None = None,
    travel_class: int | None = None,
    sort_by: int | None = None,
    stops: int | None = None,
    include_airlines: str | None = None,
    exclude_airlines: str | None = None,
    bags: int | None = None,
    max_price: str | None = None,
    outbound_times: str | None = None,
    return_times: str | None = None,
    emissions: int | None = None,
    layover_duration: str | None = None,
    exclude_conns: str | None = None,
    max_duration: str | None = None,
    show_hidden: bool | None = None,
    exclude_basic: bool | None = None,
    deep_search: bool | None = None,
    no_cache: bool | None = None,
):
    params = _build_serpapi_params(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
        return_date=return_date,
        gl=gl,
        hl=hl,
        currency=currency,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        travel_class=travel_class,
        sort_by=sort_by,
        stops=stops,
        include_airlines=include_airlines,
        exclude_airlines=exclude_airlines,
        bags=bags,
        max_price=max_price,
        outbound_times=outbound_times,
        return_times=return_times,
        emissions=emissions,
        layover_duration=layover_duration,
        exclude_conns=exclude_conns,
        max_duration=max_duration,
        show_hidden=show_hidden,
        exclude_basic=exclude_basic,
        deep_search=deep_search,
        no_cache=no_cache,
    )

    res = _serpapi_request_cached(params)
    meta = {
        "asOf": res["fetched_at"],
        "fromCache": res["from_cache"],
        "searchKey": res["search_key"],
        "snapshotId": res["snapshot_id"],
        "currency": currency,
    }

    flights = _map_serpapi_flights(res["data"], meta)
    found = _find_flight_by_uid_or_signature(flights, flight_uid, params)
    if not found:
        raise HTTPException(status_code=404, detail="Flight not found in this search snapshot.")
    return found


@router.get("/api/price-insights")
def get_price_insights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    type: Optional[int] = Query(None),
    return_date: str | None = None,
    gl: str | None = None,
    hl: str | None = None,
    currency: str | None = None,
    adults: int = 1,
    travel_class: int | None = None,
    no_cache: bool | None = None,
):
    params = _build_serpapi_params(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
        return_date=return_date,
        gl=gl,
        hl=hl,
        currency=currency,
        adults=adults,
        children=None,
        infants_in_seat=None,
        infants_on_lap=None,
        travel_class=travel_class,
        sort_by=None,
        stops=None,
        include_airlines=None,
        exclude_airlines=None,
        bags=None,
        max_price=None,
        outbound_times=None,
        return_times=None,
        emissions=None,
        layover_duration=None,
        exclude_conns=None,
        max_duration=None,
        show_hidden=None,
        exclude_basic=None,
        deep_search=None,
        no_cache=no_cache,
    )

    res = _serpapi_request_cached(params)
    data = res["data"]

    return {
        "asOf": res["fetched_at"],
        "fromCache": res["from_cache"],
        "searchKey": res["search_key"],
        "snapshotId": res["snapshot_id"],
        "price_insights": data.get("price_insights"),
        "search_parameters": data.get("search_parameters") or {},
    }


@router.get("/api/flights/{flight_uid}/price-history")
def price_history(
    flight_uid: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    type: Optional[int] = Query(None),
    return_date: str | None = None,
    gl: str | None = None,
    hl: str | None = None,
    currency: str | None = None,
    adults: int = 1,
    travel_class: int | None = None,
    no_cache: bool | None = None,
):
    params = _build_serpapi_params(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
        return_date=return_date,
        gl=gl,
        hl=hl,
        currency=currency,
        adults=adults,
        children=None,
        infants_in_seat=None,
        infants_on_lap=None,
        travel_class=travel_class,
        sort_by=None,
        stops=None,
        include_airlines=None,
        exclude_airlines=None,
        bags=None,
        max_price=None,
        outbound_times=None,
        return_times=None,
        emissions=None,
        layover_duration=None,
        exclude_conns=None,
        max_duration=None,
        show_hidden=None,
        exclude_basic=None,
        deep_search=None,
        no_cache=no_cache,
    )
    res = _serpapi_request_cached(params)
    data = res["data"]
    insights = data.get("price_insights") or {}
    history = insights.get("price_history") or []

    points: list[dict[str, Any]] = []
    for item in history:
        try:
            ts = int(item[0])
            price = item[1]
        except (IndexError, TypeError, ValueError):
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        points.append({"ts": _iso_z(dt), "price": price})

    return points


@router.get("/api/flights/{flight_uid}/price-snapshots")
def price_snapshots(
    flight_uid: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    type: Optional[int] = Query(None),
    return_date: str | None = None,
    gl: str | None = None,
    hl: str | None = None,
    currency: str | None = None,
    adults: int = 1,
    children: int | None = None,
    infants_in_seat: int | None = None,
    infants_on_lap: int | None = None,
    travel_class: int | None = None,
):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    params = _build_serpapi_params(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
        return_date=return_date,
        gl=gl,
        hl=hl,
        currency=currency,
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
        travel_class=travel_class,
        sort_by=None,
        stops=None,
        include_airlines=None,
        exclude_airlines=None,
        bags=None,
        max_price=None,
        outbound_times=None,
        return_times=None,
        emissions=None,
        layover_duration=None,
        exclude_conns=None,
        max_duration=None,
        show_hidden=None,
        exclude_basic=None,
        deep_search=None,
        no_cache=None,
    )

    search_keys = _resolve_search_keys(params)
    if not search_keys:
        return []
    db_snapshots = _build_price_snapshots(
        search_keys=search_keys, flight_uid=flight_uid, currency=currency
    )
    local_history = None
    try:
        res = _serpapi_request_cached(params)
        meta = {
            "asOf": res["fetched_at"],
            "fromCache": res["from_cache"],
            "searchKey": res["search_key"],
            "snapshotId": res["snapshot_id"],
            "currency": currency,
        }
        flights = _map_serpapi_flights(res["data"], meta)
        found = _find_flight_by_uid_or_signature(flights, flight_uid, params)
        if found:
            local_history = build_local_ticket_history(
                _ticket_from_flight_for_local_history(found, params)
            )
    except Exception:
        local_history = None
    return _merge_db_and_local_price_snapshots(
        db_snapshots=db_snapshots,
        local_history=local_history,
        currency=currency,
    )
