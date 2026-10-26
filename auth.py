"""Optional JWT authentication and admin-role authorization.

Enable with AUTH_ENABLED=true and configure ADMIN_USERNAME, ADMIN_PASSWORD,
and a strong JWT_SECRET_KEY via environment variables. Never commit secrets.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

bearer_scheme = HTTPBearer(auto_error=False)


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


def _secret() -> bytes:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY must be configured with at least 32 characters")
    return secret.encode("utf-8")


def create_access_token(subject: str, role: str = "admin", expires_in: int = 3600) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + expires_in}
    def encode(obj):
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    body = f"{encode(header)}.{encode(payload)}"
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def _decode_token(token: str) -> dict[str, Any]:
    try:
        head, body, signature = token.split(".")
        signing_input = f"{head}.{body}".encode("ascii")
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        expected = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("Expired token")
        if payload.get("role") != "admin" or not payload.get("sub"):
            raise ValueError("Insufficient role")
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token") from exc


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    # Backward-compatible local mode; production deployments should enable auth.
    if not auth_enabled():
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required")
    return _decode_token(credentials.credentials)


def authenticate(login: LoginInput) -> str:
    if not auth_enabled():
        raise HTTPException(status_code=404, detail="Authentication is disabled")
    username = os.getenv("ADMIN_USERNAME", "")
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        raise HTTPException(status_code=503, detail="ADMIN_USERNAME and ADMIN_PASSWORD must be configured")
    if not hmac.compare_digest(login.username, username) or not hmac.compare_digest(login.password, password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return create_access_token(username, "admin")
