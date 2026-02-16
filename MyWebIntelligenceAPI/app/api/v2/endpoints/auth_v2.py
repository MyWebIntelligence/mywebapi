"""
Endpoints d'authentification V2 (sync)
Includes registration, login, refresh, me, forgot-password, reset-password
"""

import secrets
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.db.models import User
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
)
from app.api.dependencies import get_current_active_user_sync
from app.schemas.user import (
    Token,
    User as UserSchema,
    UserRegister,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_sync_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Authenticate and return access + refresh tokens."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check blocked
    if user.blocked_until and user.blocked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily blocked",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Reset failed attempts on successful login
    user.failed_attempts = 0
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return {
        "access_token": create_access_token(subject=user.username),
        "refresh_token": create_refresh_token(subject=user.username),
        "token_type": "bearer",
    }


@router.post("/register", response_model=Token)
def register(
    data: UserRegister,
    db: Session = Depends(get_sync_db),
):
    """Register a new user account and auto-login."""
    # Check uniqueness
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New user registered: %s", user.username)

    return {
        "access_token": create_access_token(subject=user.username),
        "refresh_token": create_refresh_token(subject=user.username),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
def refresh(
    current_user: User = Depends(get_current_active_user_sync),
):
    """Refresh the access token."""
    return {
        "access_token": create_access_token(subject=current_user.username),
        "refresh_token": create_refresh_token(subject=current_user.username),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserSchema)
def me(
    current_user: User = Depends(get_current_active_user_sync),
):
    """Get the currently authenticated user."""
    return current_user


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_sync_db),
):
    """Request a password reset token. Always returns success for security."""
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()
        # In production, send email. In dev, log the token.
        logger.info("Password reset token for %s: %s", user.email, token)

    # Always return success to avoid user enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_sync_db),
):
    """Reset password using a token."""
    user = (
        db.query(User)
        .filter(
            User.reset_token == data.token,
            User.reset_token_expires > datetime.now(timezone.utc),
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_attempts = 0
    user.blocked_until = None
    db.commit()

    logger.info("Password reset for user: %s", user.username)
    return {"message": "Password has been reset successfully"}
