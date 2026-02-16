"""
Endpoints d'administration V2 (sync)
User management, stats, access logs
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_sync_db
from app.db.models import User, Land, Expression, Domain
from app.core.security import get_password_hash
from app.api.dependencies import get_current_admin_user_sync
from app.schemas.user import (
    UserAdminResponse,
    UserListResponse,
    BlockUserRequest,
    SetRoleRequest,
    AdminStatsResponse,
    AdminUserUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/users", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_admin: Optional[bool] = Query(None),
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """List users with pagination and filters."""
    query = db.query(User)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(pattern)) | (User.email.ilike(pattern))
        )
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return UserListResponse(
        items=[UserAdminResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Get a user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check uniqueness if changing username or email
    if "username" in update_data:
        existing = db.query(User).filter(
            User.username == update_data["username"], User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")

    if "email" in update_data:
        existing = db.query(User).filter(
            User.email == update_data["email"], User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    logger.info("Admin %s updated user %d", current_user.username, user_id)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Delete a user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    logger.info("Admin %s deleted user %d (%s)", current_user.username, user_id, user.username)
    return {"message": f"User {user.username} deleted"}


@router.post("/users/{user_id}/block")
def block_user(
    user_id: int,
    data: BlockUserRequest,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Block a user, optionally for a specified duration."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.duration_hours:
        user.blocked_until = datetime.now(timezone.utc) + timedelta(hours=data.duration_hours)
    else:
        # Block indefinitely (far future)
        user.blocked_until = datetime(2099, 12, 31, tzinfo=timezone.utc)

    user.is_active = False
    db.commit()
    logger.info("Admin %s blocked user %d", current_user.username, user_id)
    return {"message": f"User {user.username} blocked"}


@router.post("/users/{user_id}/unblock")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Unblock a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.blocked_until = None
    user.is_active = True
    user.failed_attempts = 0
    db.commit()
    logger.info("Admin %s unblocked user %d", current_user.username, user_id)
    return {"message": f"User {user.username} unblocked"}


@router.post("/users/{user_id}/set-role")
def set_role(
    user_id: int,
    data: SetRoleRequest,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Change a user's admin role."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = data.is_admin
    db.commit()
    role = "admin" if data.is_admin else "user"
    logger.info("Admin %s set user %d role to %s", current_user.username, user_id, role)
    return {"message": f"User {user.username} role set to {role}"}


@router.post("/users/{user_id}/reset-password")
def force_reset_password(
    user_id: int,
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Force reset a user's password (admin generates a temporary password)."""
    import secrets

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = secrets.token_urlsafe(12)
    user.hashed_password = get_password_hash(temp_password)
    user.failed_attempts = 0
    user.blocked_until = None
    db.commit()

    logger.info("Admin %s force-reset password for user %d", current_user.username, user_id)
    return {
        "message": f"Password reset for {user.username}",
        "temporary_password": temp_password,
    }


@router.get("/stats", response_model=AdminStatsResponse)
def admin_stats(
    db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_admin_user_sync),
):
    """Get system-wide statistics."""
    now = datetime.now(timezone.utc)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    blocked_users = db.query(func.count(User.id)).filter(
        User.blocked_until != None,
        User.blocked_until > now,
    ).scalar() or 0

    total_lands = db.query(func.count(Land.id)).scalar() or 0
    total_expressions = db.query(func.count(Expression.id)).scalar() or 0
    total_domains = db.query(func.count(Domain.id)).scalar() or 0

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        total_lands=total_lands,
        total_expressions=total_expressions,
        total_domains=total_domains,
    )
