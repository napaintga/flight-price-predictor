from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator

from services.auth import (
    _authenticate_user,
    _create_session,
    _create_user,
    _delete_session,
    _extract_bearer_token,
    _get_session,
)

router = APIRouter()


class RegisterPayload(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned:
            raise ValueError("Invalid email address.")
        return cleaned

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return value


class LoginPayload(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned:
            raise ValueError("Invalid email address.")
        return cleaned


@router.post("/api/auth/register")
def register(payload: RegisterPayload):
    user = _create_user(payload.email, payload.password)
    session = _create_session(user["id"])
    return {
        "token": session["token"],
        "expiresAt": session["expires_at"],
        "user": {
            "id": user["id"],
            "email": user["email"],
            "createdAt": user["created_at"],
        },
    }


@router.post("/api/auth/login")
def login(payload: LoginPayload):
    user = _authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    session = _create_session(user["id"])
    return {
        "token": session["token"],
        "expiresAt": session["expires_at"],
        "user": {
            "id": user["id"],
            "email": user["email"],
            "createdAt": user["created_at"],
        },
    }


@router.get("/api/auth/me")
def me(authorization: Optional[str] = Header(None)):
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token.")
    session = _get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return {
        "user": {
            "id": session["user"]["id"],
            "email": session["user"]["email"],
            "createdAt": session["user"]["created_at"],
        }
    }


@router.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    token = _extract_bearer_token(authorization)
    if not token:
        return {"ok": True}
    _delete_session(token)
    return {"ok": True}
