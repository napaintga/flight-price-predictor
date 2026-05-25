from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from fastapi import HTTPException

from core import DATABASE_URL, _iso_z


def _require_db() -> None:
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")


def _log_search_history(user_id: str, params: dict[str, Any]) -> None:
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_search_history (user_id, params)
                VALUES (%s, %s)
                """,
                (user_id, Json(params)),
            )


def _list_search_history(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, params, created_at
                FROM user_search_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "id": row["id"],
            "params": row["params"],
            "createdAt": _iso_z(row["created_at"]),
        }
        for row in rows
    ]
