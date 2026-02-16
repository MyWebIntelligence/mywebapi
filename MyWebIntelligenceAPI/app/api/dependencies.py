"""
Dépendances FastAPI pour l'authentification et les autorisations
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..db.base import get_db
from ..db.session import get_sync_db
from ..db.models import User
from ..core.security import verify_token
from ..crud import crud_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dépendance pour obtenir l'utilisateur actuel à partir du token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = verify_token(token)
    if username is None:
        raise credentials_exception
    
    user = await crud_user.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dépendance pour obtenir l'utilisateur actif actuel.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dépendance pour obtenir l'utilisateur admin actuel.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


# Sync versions for V2 SYNC endpoints

def get_current_user_sync(
    db: Session = Depends(get_sync_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dépendance SYNC pour obtenir l'utilisateur actuel (V2 SYNC).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = verify_token(token)
    if username is None:
        raise credentials_exception

    # Query sync - try username first, then email
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = db.query(User).filter(User.email == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user_sync(current_user: User = Depends(get_current_user_sync)) -> User:
    """
    Dépendance SYNC pour obtenir l'utilisateur actif actuel (V2 SYNC).
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_admin_user_sync(
    current_user: User = Depends(get_current_active_user_sync),
) -> User:
    """
    Dépendance SYNC pour obtenir l'utilisateur admin actuel (V2 SYNC).
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user
