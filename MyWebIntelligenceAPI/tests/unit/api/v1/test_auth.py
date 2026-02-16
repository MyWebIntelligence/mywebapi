"""
Tests pour les endpoints d'authentification
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user
from app.schemas.user import UserCreate

pytestmark = [pytest.mark.asyncio, pytest.mark.skip(reason="Requires 'client' fixture (TestClient) not yet configured")]

async def test_login(client: AsyncClient, db: AsyncSession) -> None:
    """
    Test de la connexion d'un utilisateur.
    """
    password = "testpassword"
    user_in = UserCreate(username="testuser", password=password, email="test@example.com")
    await crud_user.create_user(db, user_in=user_in)
    
    login_data = {"username": "testuser", "password": password}
    r = await client.post("/api/v1/auth/login", data=login_data)
    assert r.status_code == 200
    token = r.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"
