import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

# Time helpers
# ---------------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_today() -> date:
    return _utc_now().date()


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------

# Generic helpers
# ---------------------------
def _build_search_key(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_search_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized = {k: v for k, v in params.items() if v is not None}
    normalized.pop("hl", None)
    normalized.pop("no_cache", None)

    if "engine" not in normalized:
        normalized["engine"] = "google_flights"

    travel_class = normalized.get("travel_class")
    if travel_class is None or travel_class == "":
        normalized["travel_class"] = 1
    else:
        try:
            normalized["travel_class"] = int(travel_class)
        except (TypeError, ValueError):
            pass

    return normalized


def _safe_mask_api_key(url: str) -> str:
    # mask api_key=... in logs
    return re.sub(r"(api_key=)[^&]+", r"\1***", url)


def _parse_int_csv(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    # keep as-is; SerpApi expects comma-separated ints
    return v


def _parse_two_letter_code(name: str, v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    vv = v.strip().lower()
    if not re.fullmatch(r"[a-z]{2}", vv):
        raise HTTPException(status_code=422, detail=f"{name} must be a 2-letter code.")
    return vv


def _parse_currency(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    vv = v.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", vv):
        raise HTTPException(status_code=422, detail="currency must be a 3-letter code (e.g. USD, EUR).")
    return vv


def _parse_iata_or_kgmid(name: str, v: str) -> str:
    vv = v.strip()
    # allow comma-separated airports and kgmid (/m/xxxx)
    # basic validation: tokens are IATA (3 uppercase) or /m/... or empty
    parts = [p.strip() for p in vv.split(",") if p.strip()]
    if not parts:
        raise HTTPException(status_code=422, detail=f"{name} must not be empty.")
    for p in parts:
        if re.fullmatch(r"[A-Z]{3}", p):
            continue
        if p.startswith("/m/") and len(p) > 3:
            continue
        raise HTTPException(status_code=422, detail=f"{name} contains invalid token: {p}")
    return ",".join(parts)


def _parse_date_str(v: str) -> str:
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return v
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Date must be YYYY-MM-DD") from exc


def _validate_type(type_: Optional[int], return_date: Optional[str]) -> Optional[int]:
    if type_ is None:
        return None
    if type_ not in (1, 2, 3):
        raise HTTPException(status_code=422, detail="type must be 1 (round), 2 (one-way), or 3 (multi-city).")
    if type_ == 1 and not return_date:
        raise HTTPException(status_code=422, detail="return_date is required when type=1 (round trip).")
    if type_ != 1 and return_date:
        # allow but warn? We'll reject to keep consistent.
        raise HTTPException(status_code=422, detail="return_date can be used only when type=1 (round trip).")
    return type_


def _validate_travel_class(travel_class: Optional[int]) -> Optional[int]:
    if travel_class is None:
        return None
    if travel_class not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="travel_class must be 1..4 (1 economy, 2 premium, 3 business, 4 first).")
    return travel_class


def _validate_nonneg(name: str, v: Optional[int], max_v: int = 20) -> Optional[int]:
    if v is None:
        return None
    if v < 0:
        raise HTTPException(status_code=422, detail=f"{name} must be >= 0.")
    if v > max_v:
        raise HTTPException(status_code=422, detail=f"{name} is too large (max {max_v}).")
    return v


def _validate_bags(bags: Optional[int], total_pax: int) -> Optional[int]:
    if bags is None:
        return None
    if bags < 0:
        raise HTTPException(status_code=422, detail="bags must be >= 0.")
    if bags > total_pax:
        raise HTTPException(status_code=422, detail="bags must not exceed total passengers (adults+children+infants_in_seat+infants_on_lap).")
    return bags


def _validate_sort_by(sort_by: Optional[int]) -> Optional[int]:
    if sort_by is None:
        return None
    if sort_by not in (1, 2, 3, 4, 5, 6):
        raise HTTPException(status_code=422, detail="sort_by must be 1..6.")
    return sort_by


def _validate_stops(stops: Optional[int]) -> Optional[int]:
    if stops is None:
        return None
    if stops not in (0, 1, 2, 3):
        raise HTTPException(status_code=422, detail="stops must be 0..3.")
    return stops


def _validate_emissions(emissions: Optional[int]) -> Optional[int]:
    if emissions is None:
        return None
    if emissions != 1:
        raise HTTPException(status_code=422, detail="emissions currently supports only 1 (less emissions only).")
    return emissions


def _validate_duration_filter(name: str, v: Optional[str]) -> Optional[str]:
    """
    layover_duration expects "min,max" (minutes).
    outbound_times expects "a,b" or "a,b,c,d" (hours).
    max_duration expects minutes integer.
    We'll keep shallow validation.
    """
    if not v:
        return None
    vv = v.strip()
    if name in ("layover_duration",):
        if not re.fullmatch(r"\d+,\d+", vv):
            raise HTTPException(status_code=422, detail=f"{name} must be like '90,330'.")
        return vv
    if name in ("outbound_times", "return_times"):
        if not re.fullmatch(r"\d{1,2},\d{1,2}(\,\d{1,2},\d{1,2})?", vv):
            raise HTTPException(status_code=422, detail=f"{name} must be like '4,18' or '4,18,3,19'.")
        return vv
    if name in ("max_duration", "max_price"):
        if not re.fullmatch(r"\d+", vv):
            raise HTTPException(status_code=422, detail=f"{name} must be an integer.")
        return vv
    return vv


def _validate_airline_codes(name: str, v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    vv = v.strip().upper()
    # allow alliances tokens too
    allowed_alliances = {"STAR_ALLIANCE", "SKYTEAM", "ONEWORLD"}
    parts = [p.strip() for p in vv.split(",") if p.strip()]
    if not parts:
        return None
    for p in parts:
        if p in allowed_alliances:
            continue
        # airline code: 2 chars, either AA or A1 etc
        if re.fullmatch(r"[A-Z0-9]{2}", p):
            continue
        raise HTTPException(status_code=422, detail=f"{name} invalid airline/alliance token: {p}")
    return ",".join(parts)


# ---------------------------

# Build SerpApi params (validated)
# ---------------------------
def _build_serpapi_params(
    *,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    # roundtrip:
    type: Optional[int],
    return_date: Optional[str],
    # localization:
    gl: Optional[str],
    hl: Optional[str],
    currency: Optional[str],
    # pax:
    adults: int,
    children: Optional[int],
    infants_in_seat: Optional[int],
    infants_on_lap: Optional[int],
    # cabin:
    travel_class: Optional[int],
    # sorting & filters:
    sort_by: Optional[int],
    stops: Optional[int],
    include_airlines: Optional[str],
    exclude_airlines: Optional[str],
    bags: Optional[int],
    max_price: Optional[str],
    outbound_times: Optional[str],
    return_times: Optional[str],
    emissions: Optional[int],
    layover_duration: Optional[str],
    exclude_conns: Optional[str],
    max_duration: Optional[str],
    # advanced:
    show_hidden: Optional[bool],
    exclude_basic: Optional[bool],
    deep_search: Optional[bool],
    no_cache: Optional[bool],
) -> dict[str, Any]:
    dep = _parse_iata_or_kgmid("departure_id", departure_id)
    arr = _parse_iata_or_kgmid("arrival_id", arrival_id)

    out_d = _parse_date_str(outbound_date)
    ret_d = _parse_date_str(return_date) if return_date else None

    type_val = _validate_type(type, ret_d)
    tclass = _validate_travel_class(travel_class)

    gl_val = _parse_two_letter_code("gl", gl) if gl else None
    hl_val = _parse_two_letter_code("hl", hl) if hl else None
    cur_val = _parse_currency(currency) if currency else None

    adults_val = _validate_nonneg("adults", adults, max_v=9) or 1
    children_val = _validate_nonneg("children", children, max_v=9) or 0
    infants_seat_val = _validate_nonneg("infants_in_seat", infants_in_seat, max_v=9) or 0
    infants_lap_val = _validate_nonneg("infants_on_lap", infants_on_lap, max_v=9) or 0

    total_pax = adults_val + children_val + infants_seat_val + infants_lap_val
    bags_val = _validate_bags(bags, total_pax)

    sort_by_val = _validate_sort_by(sort_by)
    stops_val = _validate_stops(stops)
    emissions_val = _validate_emissions(emissions)

    include_airlines_val = _validate_airline_codes("include_airlines", include_airlines)
    exclude_airlines_val = _validate_airline_codes("exclude_airlines", exclude_airlines)
    if include_airlines_val and exclude_airlines_val:
        raise HTTPException(status_code=422, detail="include_airlines and exclude_airlines can't be used together.")

    outbound_times_val = _validate_duration_filter("outbound_times", outbound_times)
    return_times_val = _validate_duration_filter("return_times", return_times)
    layover_duration_val = _validate_duration_filter("layover_duration", layover_duration)
    max_price_val = _validate_duration_filter("max_price", max_price)
    max_duration_val = _validate_duration_filter("max_duration", max_duration)

    params: dict[str, Any] = {
        "departure_id": dep,
        "arrival_id": arr,
        "outbound_date": out_d,
        "adults": adults_val,
    }

    # type: SerpApi default is 1; we include only if specified
    if type_val is not None:
        params["type"] = type_val
    if ret_d:
        params["return_date"] = ret_d

    if gl_val:
        params["gl"] = gl_val
    if hl_val:
        params["hl"] = hl_val
    if cur_val:
        params["currency"] = cur_val

    # passengers
    if children_val:
        params["children"] = children_val
    if infants_seat_val:
        params["infants_in_seat"] = infants_seat_val
    if infants_lap_val:
        params["infants_on_lap"] = infants_lap_val

    # IMPORTANT: travel_class must be numeric (1..4)
    if tclass is not None:
        params["travel_class"] = tclass

    # sorting & filters
    if sort_by_val is not None:
        params["sort_by"] = sort_by_val
    if stops_val is not None:
        params["stops"] = stops_val
    if include_airlines_val:
        params["include_airlines"] = include_airlines_val
    if exclude_airlines_val:
        params["exclude_airlines"] = exclude_airlines_val
    if bags_val is not None:
        params["bags"] = bags_val
    if max_price_val:
        params["max_price"] = max_price_val
    if outbound_times_val:
        params["outbound_times"] = outbound_times_val
    if return_times_val:
        params["return_times"] = return_times_val
    if emissions_val is not None:
        params["emissions"] = emissions_val
    if layover_duration_val:
        params["layover_duration"] = layover_duration_val
    if exclude_conns:
        params["exclude_conns"] = _parse_iata_or_kgmid("exclude_conns", exclude_conns)
    if max_duration_val:
        params["max_duration"] = max_duration_val

    # advanced flags
    if show_hidden is not None:
        params["show_hidden"] = str(bool(show_hidden)).lower()
    if exclude_basic is not None:
        params["exclude_basic"] = str(bool(exclude_basic)).lower()
    if deep_search is not None:
        params["deep_search"] = str(bool(deep_search)).lower()

    # SerpApi caching control (optional)
    if no_cache is not None:
        params["no_cache"] = str(bool(no_cache)).lower()

    return params


# ---------------------------
