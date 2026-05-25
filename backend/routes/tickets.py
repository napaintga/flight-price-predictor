from typing import Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from core import DATABASE_URL, _iso_z, _utc_now
from services.auth import _require_user_from_auth_header
from services.local_ticket_history import build_local_ticket_history

router = APIRouter()


def _require_db() -> None:
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")


class TicketPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    flightId: str
    createdAt: Optional[str] = None


class LocalTicketHistoryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    flightId: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    airline: Optional[str] = None
    departAt: Optional[str] = None
    createdAt: Optional[str] = None
    currency: Optional[str] = None
    durationMinutes: Optional[int] = None
    stops: Optional[int] = None
    travelClass: Optional[str] = None
    tripType: Optional[str] = None
    passengers: Optional[int] = None
    searchParams: Optional[str] = None


@router.get("/api/tickets")
def list_tickets(
    flightId: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    user = _require_user_from_auth_header(authorization)
    _require_db()

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ticket, created_at
                FROM user_tickets
                WHERE user_id = %s
                  AND (%s IS NULL OR ticket->>'flightId' = %s)
                ORDER BY created_at DESC
                """,
                (user["id"], flightId, flightId),
            )
            rows = cur.fetchall()

    tickets: list[dict] = []
    for row in rows:
        ticket = row.get("ticket") or {}
        if "createdAt" not in ticket:
            ticket["createdAt"] = _iso_z(row["created_at"])
        tickets.append(ticket)
    return tickets


@router.post("/api/tickets")
def add_ticket(payload: TicketPayload, authorization: Optional[str] = Header(None)):
    user = _require_user_from_auth_header(authorization)
    _require_db()
    ticket = payload.model_dump()
    if not ticket.get("createdAt"):
        ticket["createdAt"] = _iso_z(_utc_now())

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_tickets (user_id, ticket_id, ticket)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, ticket_id)
                DO UPDATE SET ticket = EXCLUDED.ticket, created_at = now()
                """,
                (user["id"], payload.id, Json(ticket)),
            )
    return ticket


@router.post("/api/tickets/local-history")
def local_ticket_history(payload: LocalTicketHistoryPayload):
    return build_local_ticket_history(payload.model_dump(exclude_none=True))


@router.delete("/api/tickets/{ticket_id}")
def remove_ticket(ticket_id: str, authorization: Optional[str] = Header(None)):
    user = _require_user_from_auth_header(authorization)
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_tickets
                WHERE user_id = %s AND ticket_id = %s
                """,
                (user["id"], ticket_id),
            )
    return {"ok": True}
