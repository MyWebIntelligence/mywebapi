"""
Endpoints pour l'authentification
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.crud import crud_user
from app.db import models
from app.core import security
from app.api import dependencies

router = APIRouter()

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    db: AsyncSession = Depends(dependencies.get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Obtenir un token d'accès et de rafraîchissement.
    """
    user = await crud_user.user.get_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token = security.create_access_token(subject=user.username)
    refresh_token = security.create_refresh_token(subject=user.username)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """
    Rafraîchir le token d'accès.
    """
    access_token = security.create_access_token(subject=current_user.username)
    refresh_token = security.create_refresh_token(subject=current_user.username)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.get("/me", response_model=schemas.User)
def read_users_me(
    current_user: models.User = Depends(dependencies.get_current_active_user),
):
    """
    Obtenir l'utilisateur actuel.
    """
    return current_user
