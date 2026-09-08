"""Student-only registration; administrator provisioning stays out of HTTP signup."""
from __future__ import annotations

import re
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Please enter a valid email address")
        return value

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name is required")
        return value


def create_student(payload: RegistrationRequest) -> None:
    # Import at call time so the active database configuration is always respected.
    from scripts import db

    conn = db.get_conn()
    try:
        cur = db._execute(
            conn,
            "INSERT INTO app_users (email,display_name,role,password_hash,status) "
            f"VALUES ({','.join([db._ph()] * 5)}) ON CONFLICT(email) DO NOTHING",
            (payload.email, payload.display_name, "student", db._hash_password(payload.password), "active"),
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail="该邮箱已被使用，请登录或更换邮箱。")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
