"""
Fonctions utilitaires pour les tests
"""

from typing import Dict
from httpx import AsyncClient
from app import schemas

async def get_user_token_headers(client: AsyncClient, username: str, password: str) -> Dict[str, str]:
    """
    Obtenir les headers d'authentification pour un utilisateur.
    """
    login_data = {
        "username": username,
        "password": password,
    }
    r = await client.post("/api/v1/auth/login", data=login_data)
    token = r.json()
    a_token = token["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers
