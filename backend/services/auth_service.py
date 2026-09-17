"""
Authentication Service for CogniFlow
Provides secure bcrypt password hashing, JWT session tokens, and FastAPI security dependencies.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Request, Header, HTTPException, status

from backend.services.db_service import get_user_by_id

JWT_SECRET = os.getenv("JWT_SECRET", "cogniflow-jwt-production-auth-secret-key-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 14

EMAIL_REGEX = re.compile(r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,}$")


def validate_email_format(email: str) -> bool:
    if not email or len(email) > 255:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_password_strength(password: str) -> tuple[bool, str]:
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    return True, ""


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# FastAPI Auth Dependencies
# ---------------------------------------------------------------------------

def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not isinstance(authorization, str):
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Enforce authenticated user from verified JWT bearer token.
    Derives userId strictly from server-validated token payload.
    """
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session."
        )

    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account does not exist or has been removed."
        )

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
    }


from dataclasses import dataclass
import uuid

@dataclass
class CallerIdentity:
    user_id: str
    is_authenticated: bool
    is_admin: bool
    role: str
    session_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


ADMIN_EMAILS = {"admin@cogniflow.local", "admin@cogniflow.test", "admin@demo.cogniflow", "admin@cogniflow.ai"}


def is_admin_user(user: Dict[str, Any], payload: Optional[Dict[str, Any]] = None) -> bool:
    if payload and payload.get("role") == "admin":
        return True
    if user.get("role") == "admin":
        return True
    if user.get("email", "").lower() in ADMIN_EMAILS:
        return True
    if os.getenv("ADMIN_USER_ID") and user.get("id") == os.getenv("ADMIN_USER_ID"):
        return True
    return False


async def resolve_caller_identity(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
    request: Optional[Request] = None
) -> CallerIdentity:
    """
    Authoritatively resolves the requesting caller's identity.
    Strictly verifies JWT tokens, prevents x-user-id header spoofing,
    and isolates guest sessions from registered user accounts without a shared dev-user.
    """
    token = extract_token_from_header(authorization)
    raw_session = x_session_id if isinstance(x_session_id, str) else None
    clean_session = raw_session.strip() if raw_session else None

    raw_user_id = x_user_id if isinstance(x_user_id, str) else None
    clean_x = raw_user_id.strip() if raw_user_id else None

    # Path 1: Authenticated via JWT bearer token
    if token:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token."
            )

        user = get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account associated with token does not exist."
            )

        # Anti-spoofing check: if x-user-id header is sent, it MUST match the token's authenticated sub
        if clean_x:
            if clean_x != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Spoofing detected: x-user-id header does not match authenticated JWT token identity."
                )

        admin_flag = is_admin_user(user, payload)
        if request and hasattr(request, "state") and clean_session:
            request.state.session_id = clean_session

        return CallerIdentity(
            user_id=user["id"],
            session_id=clean_session,
            is_authenticated=True,
            is_admin=admin_flag,
            role="admin" if admin_flag else "user",
            email=user["email"],
            name=user.get("name")
        )

    # Anti-spoofing checks for unauthenticated callers:
    if clean_x:
        if clean_x.startswith("user_") or get_user_by_id(clean_x) is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Cannot claim registered user identity without a valid bearer token."
            )
        if clean_x in ["admin", "system", "root"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Cannot claim administrative identity without a valid bearer token."
            )

    # Path 2: Unauthenticated / Guest session resolution
    # Client cannot arbitrarily choose or impersonate a session ID.
    # The server authoritatively validates candidate tokens against active sessions.
    # If missing, invalid, or forged, a brand new server-issued session is created.
    from backend.services.guest_session_service import guest_session_service
    guest_session = guest_session_service.resolve_valid_session(clean_session)
    effective_session_id = guest_session.session_id

    if request and hasattr(request, "state"):
        request.state.session_id = effective_session_id

    return CallerIdentity(
        user_id=effective_session_id,
        session_id=effective_session_id,
        is_authenticated=False,
        is_admin=False,
        role="guest",
        email=f"{effective_session_id}@cogniflow.local",
        name="Guest Workspace"
    )


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
    request: Optional[Request] = None
) -> Optional[Dict[str, Any]]:
    """
    Returns authenticated user if valid token present,
    or falls back to isolated guest session identity resolving anti-spoofing constraints.
    """
    identity = await resolve_caller_identity(
        authorization=authorization,
        x_user_id=x_user_id,
        x_session_id=x_session_id,
        request=request
    )
    return {
        "id": identity.user_id,
        "session_id": identity.session_id,
        "email": identity.email or f"{identity.user_id}@cogniflow.local",
        "name": identity.name or identity.user_id,
        "is_authenticated": identity.is_authenticated,
        "is_admin": identity.is_admin,
        "role": identity.role
    }


