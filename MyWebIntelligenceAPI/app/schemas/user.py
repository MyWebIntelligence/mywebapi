"""
Schémas Pydantic pour les utilisateurs et l'authentification
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime

# Schéma de base pour un utilisateur
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    is_active: bool = True
    is_superuser: bool = False

# Schéma pour la création d'un utilisateur
class UserCreate(UserBase):
    password: str

# Schéma pour la mise à jour d'un utilisateur
class UserUpdate(UserBase):
    password: Optional[str] = None

# Schéma pour l'affichage d'un utilisateur (sans mot de passe)
class User(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None

# Schéma pour le token JWT
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# Schéma pour les données contenues dans le token
class TokenData(BaseModel):
    username: Optional[str] = None


# ─── Registration & Admin Schemas (V2) ──────────────────────────

class UserRegister(BaseModel):
    """Schema for public user registration."""
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_length(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserAdminResponse(BaseModel):
    """Extended user info for admin views."""
    id: int
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None
    failed_attempts: int = 0
    blocked_until: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list for admin."""
    items: List[UserAdminResponse]
    total: int
    page: int
    page_size: int


class BlockUserRequest(BaseModel):
    duration_hours: Optional[int] = None  # None = indefinite


class SetRoleRequest(BaseModel):
    is_admin: bool


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    blocked_users: int
    total_lands: int
    total_expressions: int
    total_domains: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class AdminUserUpdate(BaseModel):
    """Schema for admin user updates (all fields optional)."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
