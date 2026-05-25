from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core import _build_serpapi_params, _iso_z, _utc_now
from db.ops import _db_get_latest_prediction
from services.flight_price_model import predict_flight_price
from services.local_ticket_history import estimate_ticket_price_trend_per_day
from services.serpapi import (
    _find_flight_signature_in_snapshots,
    _flight_signature_from_flight,
    _flight_signature_route_from_flight,
    _flight_signature_weak_from_flight,
    _map_serpapi_flights,
    _serpapi_request_cached,
)

router = APIRouter()


def _db_prediction_response(flight_uid: str) -> dict | None:
    prediction = _db_get_latest_prediction(flight_uid)
    if not prediction:
        return None

    created_at = _iso_z(prediction["created_at"])
    model_name = prediction.get("model_name") or "ml-ensemble"
    return {
        "flightId": flight_uid,
        "flightUid": flight_uid,
        "predictedPrice": float(prediction["predicted_price"])
        if prediction["predicted_price"] is not None
        else None,
        "lower": float(prediction["lower"]) if prediction["lower"] is not None else None,
        "upper": float(prediction["upper"]) if prediction["upper"] is not None else None,
        "confidence": None,
        "model": model_name,
        "modelName": model_name,
        "horizonDays": prediction.get("horizon_days"),
        "updatedAt": created_at,
        "createdAt": created_at,
    }


def _stub_prediction_response(flight_uid: str) -> dict:
    generated_at = _iso_z(_utc_now())
    return {
        "flightId": flight_uid,
        "flightUid": flight_uid,
        "predictedPrice": None,
        "confidence": None,
        "model": "stub",
        "modelName": "stub",
        "horizonDays": None,
        "updatedAt": generated_at,
        "createdAt": generated_at,
    }


def _find_flight_for_prediction(
    flight_uid: str,
    params: dict,
    currency: str | None,
) -> dict | None:
    res = _serpapi_request_cached(params)
    meta = {
        "asOf": res["fetched_at"],
        "fromCache": res["from_cache"],
        "searchKey": res["search_key"],
        "snapshotId": res["snapshot_id"],
        "currency": currency,
    }
    flights = _map_serpapi_flights(res["data"], meta)
    found = next((flight for flight in flights if flight.get("uid") == flight_uid), None)
    if found:
        return found

    signature, signature_weak, signature_route = _find_flight_signature_in_snapshots(
        res["search_key"],
        flight_uid,
    )
    if signature:
        found = next(
            (
                flight
                for flight in flights
                if _flight_signature_from_flight(flight) == signature
            ),
            None,
        )
    if not found and signature_weak:
        found = next(
            (
                flight
                for flight in flights
                if _flight_signature_weak_from_flight(flight) == signature_weak
            ),
            None,
        )
    if not found and signature_route:
        found = next(
            (
                flight
                for flight in flights
                if _flight_signature_route_from_flight(flight) == signature_route
            ),
            None,
        )
    return found


def _prediction_trend_ticket(flight_uid: str, flight: dict, params: dict, currency: str | None) -> dict:
    segments = flight.get("segments") or []
    first = segments[0] if segments else {}
    last = segments[-1] if segments else {}
    return {
        "id": f"L-{flight_uid}",
        "flightId": flight_uid,
        "origin": flight.get("origin") or (first.get("departure_airport") or {}).get("id") or params.get("departure_id"),
        "destination": flight.get("destination") or (last.get("arrival_airport") or {}).get("id") or params.get("arrival_id"),
        "airline": flight.get("airline") or first.get("airline"),
        "departAt": flight.get("departAt") or (first.get("departure_airport") or {}).get("time"),
        "currency": flight.get("currency") or currency,
        "durationMinutes": flight.get("total_duration_minutes"),
        "stops": flight.get("stops"),
        "tripType": params.get("type"),
        "travelClass": params.get("travel_class"),
    }


@router.get("/api/predictions/flight/{flight_uid}")
def predict_flight(
    flight_uid: str,
    departure_id: str | None = Query(None),
    arrival_id: str | None = Query(None),
    outbound_date: str | None = Query(None),
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
    has_search_context = bool(departure_id and arrival_id and outbound_date)
    if has_search_context:
        params = _build_serpapi_params(
            departure_id=departure_id or "",
            arrival_id=arrival_id or "",
            outbound_date=outbound_date or "",
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
        flight = _find_flight_for_prediction(flight_uid, params, currency)
        if not flight:
            raise HTTPException(
                status_code=404,
                detail="Flight not found for ML prediction in this search snapshot.",
            )

        params_with_trend = dict(params)
        try:
            trend = estimate_ticket_price_trend_per_day(
                _prediction_trend_ticket(flight_uid, flight, params, currency)
            )
        except Exception:
            trend = 0.0
        params_with_trend["recent_price_trend_per_day"] = trend

        prediction = predict_flight_price(flight, params_with_trend)
        generated_at = _iso_z(_utc_now())
        return {
            "flightId": flight_uid,
            "flightUid": flight_uid,
            "predictedPrice": prediction["predicted_price"],
            "lower": prediction["lower"],
            "upper": prediction["upper"],
            "currency": prediction["currency"],
            "predictions": prediction.get("predictions") or [],
            "confidence": None,
            "model": prediction["model_name"],
            "modelName": prediction["model_name"],
            "modelMae": prediction["model_mae"],
            "modelRmse": prediction["model_rmse"],
            "modelR2": prediction["model_r2"],
            "horizonDays": prediction["features"].get("days_to_departure"),
            "updatedAt": generated_at,
            "createdAt": generated_at,
            "source": "joblib",
        }

    return _db_prediction_response(flight_uid) or _stub_prediction_response(flight_uid)
