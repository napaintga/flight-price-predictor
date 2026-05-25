import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Optional

import psycopg2
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException

from core import DATABASE_URL, _utc_now
from core.settings import AUTH_SESSION_TTL_HOURS

_HASH_NAME = "sha256"
_HASH_ITERATIONS = 260_000
_SALT_BYTES = 16


def _require_db() -> None:
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"pbkdf2_{_HASH_NAME}${_HASH_ITERATIONS}${salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iter_str, salt_hex, hash_hex = stored.split("$")
        if not algo.startswith("pbkdf2_"):
            return False
        iterations = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        _HASH_NAME, password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, expected)


def _get_user_by_email(email: str) -> Optional[dict]:
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, created_at
                FROM users
                WHERE email = %s
                """,
                (_normalize_email(email),),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _get_user_by_id(user_id: str) -> Optional[dict]:
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, created_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _create_user(email: str, password: str) -> dict:
    _require_db()
    user_id = uuid.uuid4().hex
    password_hash = _hash_password(password)
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, created_at
                    """,
                    (user_id, _normalize_email(email), password_hash),
                )
                row = cur.fetchone()
                return dict(row)
    except IntegrityError as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Email already registered.") from exc
        raise


def _create_session(user_id: str) -> dict:
    _require_db()
    token = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(hours=AUTH_SESSION_TTL_HOURS)
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_sessions (token, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (token, user_id, expires_at),
            )
    return {"token": token, "expires_at": expires_at}


def _get_session(token: str) -> Optional[dict]:
    _require_db()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.token, s.expires_at, u.id, u.email, u.created_at
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = %s
                """,
                (token,),
            )
            row = cur.fetchone()
            if not row:
                return None
            expires_at = row["expires_at"]
            if expires_at <= _utc_now():
                cur.execute("DELETE FROM user_sessions WHERE token = %s", (token,))
                return None
            return {
                "token": row["token"],
                "expires_at": expires_at,
                "user": {
                    "id": row["id"],
                    "email": row["email"],
                    "created_at": row["created_at"],
                },
            }


def _delete_session(token: str) -> None:
    if not DATABASE_URL or not token:
        return
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE token = %s", (token,))


def _authenticate_user(email: str, password: str) -> Optional[dict]:
    user = _get_user_by_email(email)
    if not user:
        return None
    stored_hash = user.get("password_hash") or ""
    if not _verify_password(password, stored_hash):
        return None
    return user


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _get_user_from_auth_header(authorization: Optional[str]) -> Optional[dict]:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    session = _get_session(token)
    if not session:
        return None
    return session["user"]


def _require_user_from_auth_header(authorization: Optional[str]) -> dict:
    user = _get_user_from_auth_header(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user
