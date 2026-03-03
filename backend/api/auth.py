# JWT verification for Supabase Auth; required for /api/chat and session endpoints.
# Supports Supabase JWT Signing Keys (JWKS / ES256) and optional Legacy HS256 secret.

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status

_backend = Path(__file__).resolve().parent.parent
_config_py = _backend / "config.py"
_spec = importlib.util.spec_from_file_location("_auth_config", _config_py)
assert _spec is not None and _spec.loader is not None
_auth_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auth_config)

SUPABASE_URL = getattr(_auth_config, "SUPABASE_URL", "").strip()
SUPABASE_JWT_SECRET = getattr(_auth_config, "SUPABASE_JWT_SECRET", "").strip()

# JWKS URL for Supabase JWT Signing Keys (ES256/RS256). Derived from SUPABASE_URL.
JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""

# Lazy-initialized JWKS client (caches keys). None if no SUPABASE_URL.
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient | None:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if not JWKS_URL:
        return None
    try:
        _jwks_client = jwt.PyJWKClient(JWKS_URL)
        return _jwks_client
    except Exception:
        return None


def _verify_with_jwks(token: str) -> dict | None:
    """Verify JWT using JWKS (ES256/RS256). Returns payload on success, None on failure.
    Raises jwt.ExpiredSignatureError if token is expired (caller should map to 401)."""
    client = _get_jwks_client()
    if not client:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise
    except (jwt.InvalidTokenError, Exception):
        return None


def get_required_user_id(request: Request) -> UUID:
    """Verify Authorization Bearer token (Supabase JWT) and return user_id. Raises 401 if missing or invalid."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Sign in and send Bearer token.",
        )
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )

    # Require at least one verification method (JWKS or Legacy).
    if not JWKS_URL and not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server auth not configured (SUPABASE_URL or SUPABASE_JWT_SECRET).",
        )

    payload = None

    # Try JWKS first (Supabase JWT Signing Keys).
    if JWKS_URL:
        try:
            payload = _verify_with_jwks(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired. Sign in again.",
            )

    # Fallback to Legacy HS256 if JWKS failed or not configured.
    if payload is None and SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired. Sign in again.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Sign in again.",
            )

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Sign in again.",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
        )
    try:
        return UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token.",
        )


# FastAPI dependency for routes that require an authenticated user.
RequireAuth = Annotated[UUID, Depends(get_required_user_id)]
