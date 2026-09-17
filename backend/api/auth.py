"""
Authentication API Router for CogniFlow
Endpoints for User Registration, Login, Logout, and Identity Verification.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from backend.models import (
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthResponse,
    UserSafe
)
from backend.services.db_service import (
    create_user,
    get_user_by_email
)
from backend.services.auth_service import (
    validate_email_format,
    validate_password_strength,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(req: AuthRegisterRequest):
    name = (req.name or "").strip()
    email = (req.email or "").strip().lower()
    password = req.password or ""
    confirm_pwd = req.confirm_password

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required."
        )

    if not validate_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    is_valid_pwd, pwd_error = validate_password_strength(password)
    if not is_valid_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=pwd_error
        )

    if confirm_pwd is not None and password != confirm_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )

    # Check duplicate email
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists."
        )

    pwd_hash = hash_password(password)
    user = create_user(email=email, name=name, password_hash=pwd_hash)

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"]
    })

    return AuthResponse(
        ok=True,
        token=token,
        user=UserSafe(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            createdAt=user["created_at"]
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: AuthLoginRequest):
    email = (req.email or "").strip().lower()
    password = req.password or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        # Generic error to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials and try again."
        )

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"]
    })

    return AuthResponse(
        ok=True,
        token=token,
        user=UserSafe(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            createdAt=user["created_at"]
        )
    )


@router.post("/logout")
async def logout():
    return {"ok": True, "message": "Successfully logged out."}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"ok": True, "user": current_user}
