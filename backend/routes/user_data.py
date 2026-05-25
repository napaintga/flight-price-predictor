from typing import Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from core import DATABASE_URL, _iso_z, _utc_now
from services.auth import _require_user_from_auth_header
from services.user_data import _list_search_history

router = APIRouter()


def _require_db() -> None:
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")


class FavoriteTicketPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    flightId: str
    createdAt: Optional[str] = None


@router.get("/api/user/search-history")
def get_search_history(
    authorization: Optional[str] = Header(None),
    limit: int = Query(6, ge=1, le=50),
):
    user = _require_user_from_auth_header(authorization)
    return _list_search_history(user["id"], limit)


@router.get("/api/user/favorites")
def list_favorites(authorization: Optional[str] = Header(None)):
    user = _require_user_from_auth_header(authorization)
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ticket, created_at
                FROM user_favorite_tickets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user["id"],),
            )
            rows = cur.fetchall()

    favorites: list[dict] = []
    for row in rows:
        ticket = row.get("ticket") or {}
        if "createdAt" not in ticket:
            ticket["createdAt"] = _iso_z(row["created_at"])
        favorites.append(ticket)
    return favorites


@router.post("/api/user/favorites")
def add_favorite(
    payload: FavoriteTicketPayload, authorization: Optional[str] = Header(None)
):
    user = _require_user_from_auth_header(authorization)
    _require_db()
    ticket = payload.model_dump()
    if not ticket.get("createdAt"):
        ticket["createdAt"] = _iso_z(_utc_now())
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_favorite_tickets (user_id, ticket_id, ticket)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, ticket_id)
                DO UPDATE SET ticket = EXCLUDED.ticket, created_at = now()
                """,
                (user["id"], payload.id, Json(ticket)),
            )
    return ticket


@router.delete("/api/user/favorites/{ticket_id}")
def remove_favorite(ticket_id: str, authorization: Optional[str] = Header(None)):
    user = _require_user_from_auth_header(authorization)
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_favorite_tickets
                WHERE user_id = %s AND ticket_id = %s
                """,
                (user["id"], ticket_id),
            )
    return {"ok": True}
