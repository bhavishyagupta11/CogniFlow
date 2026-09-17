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
from fastapi import Header, HTTPException, status

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
    if not authorization:
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

@dataclass
class CallerIdentity:
    user_id: str
    is_authenticated: bool
    is_admin: bool
    role: str
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
    x_user_id: Optional[str] = Header(None)
) -> CallerIdentity:
    """
    Authoritatively resolves the requesting caller's identity.
    Strictly verifies JWT tokens, prevents x-user-id header spoofing,
    and isolates guest/dev workspaces from registered user accounts.
    """
    token = extract_token_from_header(authorization)

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
        if x_user_id and x_user_id.strip():
            clean_x = x_user_id.strip()
            if clean_x != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Spoofing detected: x-user-id header does not match authenticated JWT token identity."
                )

        admin_flag = is_admin_user(user, payload)
        return CallerIdentity(
            user_id=user["id"],
            is_authenticated=True,
            is_admin=admin_flag,
            role="admin" if admin_flag else "user",
            email=user["email"],
            name=user.get("name")
        )

    # Path 2: Unauthenticated / Guest workspace
    if x_user_id and x_user_id.strip():
        clean_x = x_user_id.strip()
        # Anti-spoofing: An unauthenticated caller CANNOT claim an authenticated user account
        if clean_x.startswith("user_") or get_user_by_id(clean_x) is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Cannot claim registered user identity without a valid bearer token."
            )
        # Anti-spoofing: An unauthenticated caller CANNOT claim admin or system privilege
        if clean_x in ["admin", "system", "root"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Cannot claim administrative identity without a valid bearer token."
            )
        if clean_x in ["dev-user", "guest", "user_default"]:
            return CallerIdentity(
                user_id="dev-user",
                is_authenticated=False,
                is_admin=False,
                role="guest",
                email="guest@cogniflow.local",
                name="Guest Workspace"
            )
        # Any other unauthenticated string defaults safely to guest workspace
        return CallerIdentity(
            user_id="dev-user",
            is_authenticated=False,
            is_admin=False,
            role="guest",
            email="guest@cogniflow.local",
            name="Guest Workspace"
        )

    # Path 3: Default Guest / Dev Workspace
    return CallerIdentity(
        user_id="dev-user",
        is_authenticated=False,
        is_admin=False,
        role="guest",
        email="guest@cogniflow.local",
        name="Guest Workspace"
    )


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Returns authenticated user if valid token present,
    or falls back to safe identity resolving anti-spoofing constraints.
    """
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id)
    return {
        "id": identity.user_id,
        "email": identity.email or f"{identity.user_id}@cogniflow.local",
        "name": identity.name or identity.user_id,
        "is_authenticated": identity.is_authenticated,
        "is_admin": identity.is_admin,
        "role": identity.role
    }

