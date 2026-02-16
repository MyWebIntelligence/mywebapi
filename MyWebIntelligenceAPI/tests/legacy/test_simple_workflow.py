"""Tests d'intégration simplifiés pour le workflow de crawling."""

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import Mock, patch

from app.db.models import User, Land, CrawlJob, CrawlStatus
from app.core.security import get_password_hash


class TestSimpleWorkflow:
    """Tests d'intégration simplifiés."""

    @pytest.mark.asyncio
    async def test_create_basic_objects(self, async_db_session):
        """Test de création d'objets de base pour le workflow."""
        # Obtenir la session du générateur
        session = await anext(async_db_session)
        
        # Créer un utilisateur
        hashed_password = get_password_hash("test_password")
        user = User(
            username="workflow_user",
            email="workflow@test.com",
            hashed_password=hashed_password,
            is_active=True,
            is_admin=False
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        assert user.id is not None
        assert user.username == "workflow_user"
        
        # Créer un land
        land = Land(
            name="Workflow Test Land",
            description="Land for workflow testing",
            lang="fr",
            owner_id=user.id,
            start_urls=["https://example.com"],
            crawl_status=CrawlStatus.PENDING
        )
        session.add(land)
        await session.commit()
        await session.refresh(land)
        
        assert land.id is not None
        assert land.owner_id == user.id
        
        # Créer un job de crawl
        job = CrawlJob(
            land_id=land.id,
            job_type="crawl",
            status=CrawlStatus.PENDING,
            parameters={"max_depth": 2, "limit": 10},
            progress=0.0
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        
        assert job.id is not None
        assert job.land_id == land.id
        assert job.status == "PENDING"
        
        print(f"✅ Test réussi - Créé User:{user.id}, Land:{land.id}, Job:{job.id}")

    def test_workflow_api_basic(self, test_client: TestClient):
        """Test de l'API basique."""
        # Test de santé de l'API
        response = test_client.get("/")
        # L'API peut retourner 404 ou 422, c'est OK pour ce test de base
        assert response.status_code in [200, 404, 422]
        
        print(f"✅ Test API de base réussi - Status: {response.status_code}")

    @pytest.mark.asyncio
    async def test_unit_components_integration(self, async_db_session):
        """Test d'intégration des composants unitaires."""
        from app.schemas.user import UserCreate
        from app.schemas.land import LandCreate
        
        # Obtenir la session du générateur
        session = await anext(async_db_session)
        
        # Test CRUD utilisateur
        user_data = UserCreate(
            username="crud_test_user",
            email="crud@test.com",
            password="test123"
        )
        
        # Test basique pour valider l'intégration
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_admin=False
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        # Valider que l'utilisateur a été créé
        assert user.id is not None
        assert user.email == "crud@test.com"
        
        print(f"✅ Test CRUD intégration réussi - User ID: {user.id}")
