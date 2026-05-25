import json
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json

from core import DATABASE_URL, _build_search_key, _normalize_search_params, _utc_now, _utc_today

# DB (daily snapshots)
# ---------------------------
def _ensure_db() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is not configured. Skipping DB init.")
        return
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS serpapi_searches (
                    search_key TEXT PRIMARY KEY,
                    params JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS serpapi_search_snapshots (
                    id BIGSERIAL PRIMARY KEY,
                    search_key TEXT NOT NULL REFERENCES serpapi_searches(search_key) ON DELETE CASCADE,
                    response JSONB NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    fetched_date DATE NOT NULL DEFAULT (now() AT TIME ZONE 'UTC')::date
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS serpapi_search_snapshots_log (
                    id BIGSERIAL PRIMARY KEY,
                    search_key TEXT NOT NULL REFERENCES serpapi_searches(search_key) ON DELETE CASCADE,
                    response JSONB NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM   pg_indexes
                        WHERE  schemaname = 'public'
                        AND    indexname = 'uq_serpapi_snapshot_day'
                    ) THEN
                        CREATE UNIQUE INDEX uq_serpapi_snapshot_day
                            ON serpapi_search_snapshots(search_key, fetched_date);
                    END IF;
                END $$;
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_serpapi_snapshots_search_key_fetched_at ON serpapi_search_snapshots(search_key, fetched_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_serpapi_snapshots_log_search_key_fetched_at ON serpapi_search_snapshots_log(search_key, fetched_at DESC);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fx_rates (
                    id BIGSERIAL PRIMARY KEY,
                    base TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    rate NUMERIC NOT NULL,
                    rate_date DATE NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM   pg_indexes
                        WHERE  schemaname = 'public'
                        AND    indexname = 'uq_fx_rates'
                    ) THEN
                        CREATE UNIQUE INDEX uq_fx_rates
                            ON fx_rates(base, quote, rate_date);
                    END IF;
                END $$;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_predictions (
                    id BIGSERIAL PRIMARY KEY,
                    flight_uid TEXT NOT NULL,
                    predicted_price NUMERIC,
                    lower NUMERIC,
                    upper NUMERIC,
                    currency TEXT,
                    horizon_days INT NOT NULL DEFAULT 7,
                    model_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_predictions_flight_uid_created ON price_predictions(flight_uid, created_at DESC);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_search_history (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    params JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_search_history_user_id_created ON user_search_history(user_id, created_at DESC);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_favorite_tickets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ticket_id TEXT NOT NULL,
                    ticket JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM   pg_indexes
                        WHERE  schemaname = 'public'
                        AND    indexname = 'uq_user_favorite_ticket'
                    ) THEN
                        CREATE UNIQUE INDEX uq_user_favorite_ticket
                            ON user_favorite_tickets(user_id, ticket_id);
                    END IF;
                END $$;
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_favorite_tickets_user_id_created ON user_favorite_tickets(user_id, created_at DESC);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tickets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ticket_id TEXT NOT NULL,
                    ticket JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM   pg_indexes
                        WHERE  schemaname = 'public'
                        AND    indexname = 'uq_user_ticket'
                    ) THEN
                        CREATE UNIQUE INDEX uq_user_ticket
                            ON user_tickets(user_id, ticket_id);
                    END IF;
                END $$;
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_tickets_user_id_created ON user_tickets(user_id, created_at DESC);"
            )


def _db_upsert_search_base(search_key: str, params: dict[str, Any]) -> None:
    if not DATABASE_URL:
        return
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO serpapi_searches (search_key, params)
                VALUES (%s, %s)
                ON CONFLICT (search_key)
                DO UPDATE SET params = EXCLUDED.params,
                              updated_at = now();
                """,
                (search_key, Json(params)),
            )


def _db_get_today_snapshot(search_key: str) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    today = _utc_today()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fetched_at, response
                FROM serpapi_search_snapshots
                WHERE search_key=%s AND fetched_date=%s
                ORDER BY fetched_at DESC
                LIMIT 1;
                """,
                (search_key, today),
            )
            row = cur.fetchone()
            if not row:
                return None
            snapshot_id, fetched_at, response = row
            return {"snapshot_id": snapshot_id, "fetched_at": fetched_at, "response": response}


def _db_get_all_snapshots(
    search_key: str | list[str], limit: int = 30
) -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    keys = [search_key] if isinstance(search_key, str) else list(search_key)
    if not keys:
        return []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fetched_at, response
                FROM serpapi_search_snapshots
                WHERE search_key = ANY(%s)
                ORDER BY fetched_at DESC
                LIMIT %s;
                """,
                (keys, limit),
            )
            rows = cur.fetchall()
            results: list[dict[str, Any]] = []
            for snapshot_id, fetched_at, response in rows:
                results.append(
                    {
                        "snapshot_id": snapshot_id,
                        "fetched_at": fetched_at,
                        "response": response,
                    }
                )
            return results


def _db_get_all_snapshots_log(
    search_key: str | list[str], limit: int = 60
) -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    keys = [search_key] if isinstance(search_key, str) else list(search_key)
    if not keys:
        return []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fetched_at, response
                FROM serpapi_search_snapshots_log
                WHERE search_key = ANY(%s)
                ORDER BY fetched_at DESC
                LIMIT %s;
                """,
                (keys, limit),
            )
            rows = cur.fetchall()
            results: list[dict[str, Any]] = []
            for snapshot_id, fetched_at, response in rows:
                results.append(
                    {
                        "snapshot_id": snapshot_id,
                        "fetched_at": fetched_at,
                        "response": response,
                    }
                )
            return results


def _db_get_latest_prediction(flight_uid: str) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT predicted_price, lower, upper, currency, horizon_days, model_name, created_at
                FROM price_predictions
                WHERE flight_uid = %s
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (flight_uid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            predicted_price, lower, upper, currency, horizon_days, model_name, created_at = row
            return {
                "predicted_price": predicted_price,
                "lower": lower,
                "upper": upper,
                "currency": currency,
                "horizon_days": horizon_days,
                "model_name": model_name,
                "created_at": created_at,
            }


def _db_find_search_keys_by_normalized_params(
    normalized_params: dict[str, Any],
) -> list[str]:
    if not DATABASE_URL:
        return []
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT search_key, params FROM serpapi_searches;")
            rows = cur.fetchall()
    matches: list[str] = []
    for search_key, params in rows:
        if not isinstance(params, dict):
            continue
        if _normalize_search_params(params) == normalized_params:
            matches.append(search_key)
    return matches


def _resolve_search_keys(params: dict[str, Any]) -> list[str]:
    store_params = {"engine": "google_flights", **params}
    normalized_params = _normalize_search_params(store_params)
    normalized_key = _build_search_key(normalized_params)
    keys = [normalized_key]
    for key in _db_find_search_keys_by_normalized_params(normalized_params):
        if key not in keys:
            keys.append(key)
    return keys


def _db_insert_snapshot(search_key: str, response: dict[str, Any]) -> dict[str, Any]:
    if not DATABASE_URL:
        return {"snapshot_id": None, "fetched_at": _utc_now(), "response": response}
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO serpapi_search_snapshots (search_key, response)
                VALUES (%s, %s)
                ON CONFLICT (search_key, fetched_date)
                DO UPDATE SET response = EXCLUDED.response,
                              fetched_at = now()
                RETURNING id, fetched_at;
                """,
                (search_key, Json(response)),
            )
            snapshot_id, fetched_at = cur.fetchone()
            return {"snapshot_id": snapshot_id, "fetched_at": fetched_at, "response": response}


def _db_insert_snapshot_log(search_key: str, response: dict[str, Any]) -> dict[str, Any]:
    if not DATABASE_URL:
        return {"snapshot_id": None, "fetched_at": _utc_now(), "response": response}
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fetched_at, response
                FROM serpapi_search_snapshots_log
                WHERE search_key = %s
                ORDER BY fetched_at DESC
                LIMIT 1;
                """,
                (search_key,),
            )
            row = cur.fetchone()
            if row:
                last_id, last_fetched_at, last_response = row
                last_sig = json.dumps(last_response, sort_keys=True, separators=(",", ":"))
                new_sig = json.dumps(response, sort_keys=True, separators=(",", ":"))
                if last_sig == new_sig:
                    return {
                        "snapshot_id": last_id,
                        "fetched_at": last_fetched_at,
                        "response": last_response,
                    }
            cur.execute(
                """
                INSERT INTO serpapi_search_snapshots_log (search_key, response)
                VALUES (%s, %s)
                RETURNING id, fetched_at;
                """,
                (search_key, Json(response)),
            )
            snapshot_id, fetched_at = cur.fetchone()
            return {"snapshot_id": snapshot_id, "fetched_at": fetched_at, "response": response}


# ---------------------------
