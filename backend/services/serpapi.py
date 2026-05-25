import hashlib
from typing import Any, Optional

import requests
from fastapi import HTTPException

from core import DATABASE_URL, SERPAPI_KEY, SERPAPI_URL, _build_search_key, _iso_z, _normalize_search_params, _safe_mask_api_key
from db.ops import (
    _db_get_all_snapshots,
    _db_get_all_snapshots_log,
    _db_get_today_snapshot,
    _db_insert_snapshot,
    _db_insert_snapshot_log,
    _db_upsert_search_base,
)

# SerpApi cached request (1/day per search_key, UTC)
# ---------------------------
def _serpapi_request_cached(params: dict[str, Any]) -> dict[str, Any]:
    if not SERPAPI_KEY:
        raise HTTPException(status_code=500, detail="SERPAPI_KEY is not configured.")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    no_cache_raw = str(params.get("no_cache", "")).lower()
    force_refresh = no_cache_raw in ("1", "true", "yes")
    params_no_cache = {k: v for k, v in params.items() if k != "no_cache"}
    store_params = {"engine": "google_flights", **params_no_cache}
    normalized_params = _normalize_search_params(store_params)
    search_key = _build_search_key(normalized_params)

    _db_upsert_search_base(search_key, normalized_params)

    if not force_refresh:
        cached = _db_get_today_snapshot(search_key)
        if cached:
            return {
                "search_key": search_key,
                "snapshot_id": cached["snapshot_id"],
                "fetched_at": _iso_z(cached["fetched_at"]),
                "from_cache": True,
                "data": cached["response"],
            }

    final_params = {**store_params, "api_key": SERPAPI_KEY}
    if "no_cache" in params:
        final_params["no_cache"] = params["no_cache"]

    try:
        resp = requests.get(SERPAPI_URL, params=final_params, timeout=30)

        # Debug logs without leaking api_key:
        print("SerpApi request URL:", _safe_mask_api_key(resp.url))
        print("SerpApi status:", resp.status_code)
        if resp.status_code != 200:
            print("SerpApi response body:", (resp.text or "")[:1200])

        resp.raise_for_status()
        data = resp.json()

        # SerpApi may return 200 with {"error": "..."}
        if isinstance(data, dict) and data.get("error"):
            raise HTTPException(status_code=502, detail=f"SerpApi error payload: {data.get('error')}")

    except requests.Timeout as exc:
        raise HTTPException(status_code=502, detail=f"SerpApi timeout: {exc}") from exc
    except HTTPException:
        raise
    except requests.RequestException as exc:
        upstream_status = getattr(getattr(exc, "response", None), "status_code", None)
        upstream_body = ""
        if getattr(exc, "response", None) is not None:
            upstream_body = (exc.response.text or "")[:1200]
        raise HTTPException(
            status_code=502,
            detail=f"SerpApi request failed. upstream_status={upstream_status}, error={exc}, body={upstream_body}",
        ) from exc

    inserted = _db_insert_snapshot(search_key, data)
    _db_insert_snapshot_log(search_key, data)
    return {
        "search_key": search_key,
        "snapshot_id": inserted["snapshot_id"],
        "fetched_at": _iso_z(inserted["fetched_at"]),
        "from_cache": False,
        "data": data,
    }


# ---------------------------

# Mapping SerpApi -> UI schema
# ---------------------------
def _format_duration(total_minutes: int | None) -> str:
    if total_minutes is None:
        return "-"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _flight_uid_from_entry(
    entry: dict[str, Any], search_parameters: Optional[dict[str, Any]] = None
) -> str:
    segments = entry.get("flights") or []
    if not segments:
        token = entry.get("booking_token") or ""
        return hashlib.sha256(f"token:{token}".encode("utf-8")).hexdigest()

    parts: list[str] = []
    for seg in segments:
        da = (seg.get("departure_airport") or {}).get("id") or ""
        dt = (seg.get("departure_airport") or {}).get("time") or ""
        aa = (seg.get("arrival_airport") or {}).get("id") or ""
        at = (seg.get("arrival_airport") or {}).get("time") or ""
        fn = seg.get("flight_number") or ""
        al = seg.get("airline") or ""
        parts.append("|".join([da, dt, aa, at, fn, al]))

    travel_class = (segments[0].get("travel_class") or entry.get("travel_class") or "").strip()
    params = search_parameters or {}
    adults = params.get("adults") or 1
    children = params.get("children") or 0
    infants_seat = params.get("infants_in_seat") or 0
    infants_lap = params.get("infants_on_lap") or 0
    pax_sig = f"{adults},{children},{infants_seat},{infants_lap}"

    base = "segments:" + "~~".join(parts) + f"|class:{travel_class}|pax:{pax_sig}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _signature_from_segments(
    segments: list[dict[str, Any]], include_times: bool, include_carrier: bool
) -> str:
    parts: list[str] = []
    for seg in segments:
        dep = seg.get("departure_airport") or {}
        arr = seg.get("arrival_airport") or {}
        parts.append(
            "|".join(
                [
                    dep.get("id") or "",
                    dep.get("time") or "" if include_times else "",
                    arr.get("id") or "",
                    arr.get("time") or "" if include_times else "",
                    seg.get("flight_number") or "" if include_carrier else "",
                    seg.get("airline") or "" if include_carrier else "",
                ]
            )
        )
    base = "segments:" + "~~".join(parts)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _flight_signature_from_flight(flight: dict[str, Any]) -> str:
    segments = flight.get("segments") or []
    return _signature_from_segments(
        segments, include_times=True, include_carrier=True
    )


def _flight_signature_weak_from_flight(flight: dict[str, Any]) -> str:
    segments = flight.get("segments") or []
    return _signature_from_segments(
        segments, include_times=False, include_carrier=True
    )


def _flight_signature_route_from_flight(flight: dict[str, Any]) -> str:
    segments = flight.get("segments") or []
    return _signature_from_segments(
        segments, include_times=False, include_carrier=False
    )


def _flight_signature_from_entry(entry: dict[str, Any]) -> str:
    segments = entry.get("flights") or []
    return _signature_from_segments(
        segments, include_times=True, include_carrier=True
    )


def _flight_signature_weak_from_entry(entry: dict[str, Any]) -> str:
    segments = entry.get("flights") or []
    return _signature_from_segments(
        segments, include_times=False, include_carrier=True
    )


def _flight_signature_route_from_entry(entry: dict[str, Any]) -> str:
    segments = entry.get("flights") or []
    return _signature_from_segments(
        segments, include_times=False, include_carrier=False
    )


def _find_flight_signature_in_snapshots(
    search_keys: str | list[str], flight_uid: str
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    snapshots_log = _db_get_all_snapshots_log(search_keys, limit=60)
    snapshots_day = _db_get_all_snapshots(search_keys, limit=60)
    snapshots: list[dict[str, Any]] = []
    if snapshots_log:
        snapshots = list(snapshots_log)
        if snapshots_day:
            snapshots.extend(snapshots_day)
    else:
        snapshots = list(snapshots_day)
    for snap in snapshots:
        data = snap.get("response") or {}
        entries = (data.get("best_flights") or []) + (data.get("other_flights") or [])
        for entry in entries:
            if _flight_uid_from_entry(entry, data.get("search_parameters") or {}) == flight_uid:
                return (
                    _flight_signature_from_entry(entry),
                    _flight_signature_weak_from_entry(entry),
                    _flight_signature_route_from_entry(entry),
                )
    return None, None, None


def _map_serpapi_flights(data: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    flights: list[dict[str, Any]] = []
    search_parameters = data.get("search_parameters") or {}
    currency = search_parameters.get("currency") or meta.get("currency") or "USD"

    def map_segment(seg: dict[str, Any]) -> dict[str, Any]:
        return {
            "airline": seg.get("airline"),
            "airline_logo": seg.get("airline_logo"),
            "flight_number": seg.get("flight_number"),
            "travel_class": seg.get("travel_class"),
            "duration": seg.get("duration"),
            "legroom": seg.get("legroom"),
            "airplane": seg.get("airplane"),
            "extensions": seg.get("extensions") or [],
            "departure_airport": seg.get("departure_airport") or {},
            "arrival_airport": seg.get("arrival_airport") or {},
        }

    def add_entries(entries: list[dict[str, Any]], is_best: bool) -> None:
        for entry in entries:
            segments = entry.get("flights") or []
            stops = max(len(segments) - 1, 0)

            origin = None
            destination = None
            depart_at = None
            arrival_at = None
            airlines = set()
            duration_minutes = entry.get("total_duration")

            if segments:
                first = segments[0]
                last = segments[-1]
                origin = (first.get("departure_airport") or {}).get("id")
                destination = (last.get("arrival_airport") or {}).get("id")
                depart_at = (first.get("departure_airport") or {}).get("time")
                arrival_at = (last.get("arrival_airport") or {}).get("time")
                for seg in segments:
                    al = seg.get("airline")
                    if al:
                        airlines.add(al)
                if duration_minutes is None:
                    duration_minutes = sum(int(seg.get("duration", 0) or 0) for seg in segments)

            entry_airline = entry.get("airline")
            airline_label = entry_airline
            if not airline_label and segments:
                airline_label = segments[0].get("airline")
            if not airline_label:
                if len(airlines) == 1:
                    airline_label = next(iter(airlines))
                elif len(airlines) > 1:
                    airline_label = next(iter(airlines))

            airline_logo = entry.get("airline_logo")
            if not airline_logo and segments:
                airline_logo = segments[0].get("airline_logo")

            uid = _flight_uid_from_entry(entry, search_parameters)

            flights.append(
                {
                    "id": len(flights),
                    "uid": uid,
                    "origin": origin or search_parameters.get("departure_id") or "",
                    "destination": destination or search_parameters.get("arrival_id") or "",
                    "departAt": depart_at or search_parameters.get("outbound_date") or "",
                    "arrivalAt": arrival_at or "",
                    "airline": airline_label,
                    "airline_logo": airline_logo,
                    "price": entry.get("price"),
                    "currency": currency,
                    "duration": _format_duration(duration_minutes),
                    "total_duration_minutes": duration_minutes,
                    "stops": stops,
                    "best": is_best,
                    "type": entry.get("type") or ("Direct" if stops == 0 else f"{stops} stops"),
                    "extensions": entry.get("extensions") or [],
                    "layovers": entry.get("layovers") or [],
                    "carbon_emissions": entry.get("carbon_emissions") or {},
                    "segments": [map_segment(seg) for seg in segments],
                    "booking_token": entry.get("booking_token"),
                    # meta:
                    "asOf": meta["asOf"],
                    "fromCache": meta["fromCache"],
                    "searchKey": meta["searchKey"],
                    "snapshotId": meta["snapshotId"],
                }
            )

    add_entries(data.get("best_flights") or [], True)
    add_entries(data.get("other_flights") or [], False)
    return flights


# ---------------------------

def _build_price_snapshots(
    *, search_keys: str | list[str], flight_uid: str, currency: Optional[str]
) -> list[dict[str, Any]]:
    key_list = [search_keys] if isinstance(search_keys, str) else list(search_keys)
    meta_key = key_list[0] if key_list else ""
    snapshots_log = _db_get_all_snapshots_log(key_list, limit=60)
    snapshots_day = _db_get_all_snapshots(key_list, limit=60)
    snapshots: list[dict[str, Any]] = []
    if snapshots_log:
        snapshots = list(snapshots_log)
        earliest_log = min(s["fetched_at"] for s in snapshots_log)
        if snapshots_day:
            snapshots.extend(
                [s for s in snapshots_day if s["fetched_at"] < earliest_log]
            )
    else:
        snapshots = list(snapshots_day)

    if not snapshots:
        return []

    snapshots.sort(key=lambda s: s["fetched_at"], reverse=True)

    (
        reference_signature,
        reference_signature_weak,
        reference_signature_route,
    ) = _find_flight_signature_in_snapshots(key_list, flight_uid)
    results: list[dict[str, Any]] = []
    for snap in snapshots:
        meta = {
            "asOf": _iso_z(snap["fetched_at"]),
            "fromCache": True,
            "searchKey": meta_key,
            "snapshotId": snap["snapshot_id"],
            "currency": currency,
        }
        flights = _map_serpapi_flights(snap["response"], meta)
        found = next((f for f in flights if f.get("uid") == flight_uid), None)
        if found:
            if reference_signature is None:
                reference_signature = _flight_signature_from_flight(found)
                reference_signature_weak = _flight_signature_weak_from_flight(found)
                reference_signature_route = _flight_signature_route_from_flight(
                    found
                )
            results.append(
                {
                    "asOf": meta["asOf"],
                    "price": found.get("price"),
                    "currency": found.get("currency"),
                    "snapshotId": meta["snapshotId"],
                }
            )
            continue
        if reference_signature:
            fallback = next(
                (f for f in flights if _flight_signature_from_flight(f) == reference_signature),
                None,
            )
            if fallback:
                results.append(
                    {
                        "asOf": meta["asOf"],
                        "price": fallback.get("price"),
                        "currency": fallback.get("currency"),
                        "snapshotId": meta["snapshotId"],
                    }
                )
                continue
        if reference_signature_weak:
            fallback = next(
                (
                    f
                    for f in flights
                    if _flight_signature_weak_from_flight(f) == reference_signature_weak
                ),
                None,
            )
            if fallback:
                results.append(
                    {
                        "asOf": meta["asOf"],
                        "price": fallback.get("price"),
                        "currency": fallback.get("currency"),
                        "snapshotId": meta["snapshotId"],
                    }
                )
                continue
        if reference_signature_route:
            fallback = next(
                (
                    f
                    for f in flights
                    if _flight_signature_route_from_flight(f)
                    == reference_signature_route
                ),
                None,
            )
            if fallback:
                results.append(
                    {
                        "asOf": meta["asOf"],
                        "price": fallback.get("price"),
                        "currency": fallback.get("currency"),
                        "snapshotId": meta["snapshotId"],
                    }
                )

    # Deduplicate consecutive identical prices (same currency) to avoid noisy repeats
    deduped: list[dict[str, Any]] = []
    last_key: tuple[str, str] | None = None
    for item in results:
        price_val = item.get("price")
        currency_val = item.get("currency") or ""
        key = (str(price_val), str(currency_val))
        if key == last_key:
            continue
        deduped.append(item)
        last_key = key

    return deduped
