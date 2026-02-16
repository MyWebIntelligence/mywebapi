"""
Tests pour l'API de crawling.

Ce module teste les fonctionnalités de crawling de l'API MyWebIntelligence,
incluant le lancement de tâches de crawling et de consolidation.

STATUT: ✅ FONCTIONNEL - Les composants suivants sont testés:
- ✅ Endpoint POST /api/v1/lands/{land_id}/crawl
- ✅ Endpoint POST /api/v1/lands/{land_id}/consolidate
- ✅ Gestion des permissions et des erreurs (401, 403, 404)

Note: Les tests sont conçus pour valider la réponse immédiate de l'API (lancement de job)
et non l'exécution complète de la tâche Celery.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.security import create_access_token
# Fonctions utilitaires pour les tests (définies localement)
def create_test_user(db, email, password):
    from app.db.models import User
    from app.core.security import get_password_hash
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_test_land(db, name, description, owner_id, start_urls=None):
    from app.db.models import Land
    land = Land(
        name=name,
        description=description,
        owner_id=owner_id,
        start_urls=start_urls or []
    )
    db.add(land)
    db.commit()
    db.refresh(land)
    return land


class TestCrawlAPI:
    """Tests pour les endpoints de crawling et de consolidation."""

    @pytest.fixture
    async def test_user_and_token(self, db_session: Session):
        """Crée un utilisateur de test et son token d'authentification."""
        user = create_test_user(db_session, email="crawl_test@example.com", password="testpass")
        token = create_access_token(data={"sub": user.email})
        return user, token

    @pytest.fixture
    async def test_land(self, db_session: Session, test_user_and_token):
        """Crée un land de test appartenant à l'utilisateur de test."""
        user, _ = test_user_and_token
        land = create_test_land(
            db_session,
            name="Test Crawl Land",
            description="Land pour tests de crawling",
            owner_id=user.id,
            start_urls=["https://example.com", "https://test.com"]
        )
        return land

    async def test_start_crawl_success(self, test_user_and_token, test_land):
        """Test du lancement réussi d'un crawl."""
        user, token = test_user_and_token

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/lands/{test_land.id}/crawl",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 202  # Accepted
        data = response.json()

        # Vérifications de la réponse
        assert "job_id" in data
        assert data["status"] == "started"
        assert "crawl job initiated" in data["message"].lower()

    async def test_start_consolidation_success(self, test_user_and_token, test_land):
        """Test du lancement réussi d'une consolidation."""
        user, token = test_user_and_token

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/lands/{test_land.id}/consolidate",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 202  # Accepted
        data = response.json()

        # Vérifications de la réponse
        assert "job_id" in data
        assert data["status"] == "started"
        assert "consolidation job initiated" in data["message"].lower()

    async def test_start_crawl_land_not_found(self, test_user_and_token):
        """Test du lancement d'un crawl sur un land inexistant."""
        user, token = test_user_and_token

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/lands/99999/crawl",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_start_crawl_unauthorized(self, test_land):
        """Test du lancement d'un crawl sans authentification."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/lands/{test_land.id}/crawl"
            )

        assert response.status_code == 401

    async def test_start_crawl_forbidden_access(self, test_land, db_session):
        """Test du lancement d'un crawl sur un land appartenant à un autre utilisateur."""
        # Créer un autre utilisateur
        other_user = create_test_user(
            db_session,
            email="other_user@example.com",
            password="otherpass"
        )
        other_token = create_access_token(data={"sub": other_user.email})

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/lands/{test_land.id}/crawl",
                headers={"Authorization": f"Bearer {other_token}"}
            )

        # Devrait être 403 (Forbidden) car le land existe mais n'appartient pas à l'utilisateur.
        assert response.status_code == 403

    async def test_start_consolidation_land_not_found(self, test_user_and_token):
        """Test du lancement d'une consolidation sur un land inexistant."""
        user, token = test_user_and_token

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/lands/99999/consolidate",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_start_consolidation_unauthorized(self, test_land):
        """Test du lancement d'une consolidation sans authentification."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/lands/{test_land.id}/consolidate"
            )

        assert response.status_code == 401


class TestCrawlJobStatus:
    """Tests pour le suivi des jobs de crawling (préparatoire)."""

    @pytest.mark.skip(reason="Endpoint /api/v1/jobs/{job_id} non implémenté.")
    async def test_get_crawl_status(self):
        """Test pour vérifier le statut d'un job de crawling."""
        # Ce test sera activé lorsque l'endpoint de suivi des jobs sera créé.
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/jobs/some-test-job-id")
        assert response.status_code == 200


class TestCrawlIntegration:
    """Tests d'intégration pour le workflow de crawling."""

    @pytest.mark.integration
    async def test_full_crawl_and_consolidate_workflow(self, test_user_and_token, test_land):
        """Test d'intégration basique du workflow de crawling et consolidation."""
        _user, token = test_user_and_token

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. Lancement du crawl
            crawl_response = await client.post(
                f"/api/v1/lands/{test_land.id}/crawl",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert crawl_response.status_code == 202
            crawl_data = crawl_response.json()
            assert "job_id" in crawl_data
            assert crawl_data["status"] == "started"

            # 2. Lancement de la consolidation
            consolidation_response = await client.post(
                f"/api/v1/lands/{test_land.id}/consolidate",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert consolidation_response.status_code == 202
            consolidation_data = consolidation_response.json()
            assert "job_id" in consolidation_data
            assert consolidation_data["status"] == "started"
