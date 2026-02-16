"""
Configuration des fixtures pour les tests MyWebIntelligence.

Ce module fournit les fixtures communes utilisées par tous les tests,
notamment pour les tests d'intégration qui nécessitent une base de données
et des objets de test.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.models import User, Land
from app.crud import user as crud_user, land as crud_land
from app.schemas.user import UserCreate
from app.schemas.land import LandCreate
from app.core.security import get_password_hash
from app.api.dependencies import get_current_user


# URL de base de données en mémoire pour les tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Fixture pour créer une boucle d'événements pour la session de test.
    
    Nécessaire pour les tests async avec pytest-asyncio.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    """
    Fixture pour créer un moteur de base de données async en mémoire.
    
    Utilise SQLite en mémoire pour des tests rapides et isolés.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )
    
    # Création des tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Nettoyage
    await engine.dispose()


@pytest.fixture
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture pour créer une session de base de données async pour chaque test.
    
    Chaque test obtient une session fraîche avec rollback automatique
    pour garantir l'isolation entre les tests.
    """
    async_session = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        # Commencer une transaction
        await session.begin()
        
        yield session
        
        # Rollback à la fin du test pour nettoyer
        await session.rollback()


@pytest.fixture
async def test_user(async_db_session: AsyncSession) -> User:
    """
    Fixture pour créer un utilisateur de test.
    
    Crée un utilisateur standard utilisé dans les tests d'intégration.
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    
    user_data = UserCreate(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        password="testpassword123",
        is_superuser=False
    )
    
    # Création de l'utilisateur
    test_user = await crud_user.create(
        db=async_db_session,
        obj_in=user_data
    )
    
    return test_user


@pytest.fixture
async def test_admin_user(async_db_session: AsyncSession) -> User:
    """
    Fixture pour créer un utilisateur administrateur de test.
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    
    admin_data = UserCreate(
        username=f"admin_{unique_id}",
        email=f"admin_{unique_id}@example.com",
        password="adminpassword123",
        is_superuser=True
    )
    
    admin = await crud_user.create(
        db=async_db_session,
        obj_in=admin_data
    )
    
    return admin


@pytest.fixture
async def test_land(async_db_session: AsyncSession, test_user: User) -> Land:
    """
    Fixture pour créer un land de test.
    
    Crée un land associé au test_user pour les tests d'intégration.
    """
    # Cast explicite pour éviter les erreurs de type
    user_id: int = test_user.id  # type: ignore
    
    land_data = LandCreate(
        name="Test Land",
        description="Land de test pour les tests d'intégration",
        lang=["fr"],
        start_urls=["https://example.com", "https://test.example.com"]
    )
    
    land = await crud_land.create(
        db=async_db_session,
        obj_in=land_data,
        owner_id=user_id
    )
    
    return land


@pytest.fixture
async def test_multiple_lands(async_db_session: AsyncSession, test_user: User) -> list[Land]:
    """
    Fixture pour créer plusieurs lands de test.
    """
    # The `test_user` parameter is already the resolved User object from the fixture.
    user_id: int = test_user.id  # type: ignore
    lands = []
    
    for i in range(3):
        land_data = LandCreate(
            name=f"Test Land {i+1}",
            description=f"Land de test {i+1}",
            lang=["fr"],
            start_urls=[f"https://example{i+1}.com"]
        )
        
        land = await crud_land.create(
            db=async_db_session,
            obj_in=land_data,
            owner_id=user_id
        )
        
        lands.append(land)
    
    return lands


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """
    Fixture pour mocker le client HTTP httpx.
    
    Utilisé pour simuler les réponses HTTP dans les tests de crawling
    sans faire de vraies requêtes réseau.
    """
    mock_client = AsyncMock()
    
    # Configuration par défaut d'une réponse HTTP réussie
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = """
    <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <h1>Test Content</h1>
            <p>This is test content</p>
        </body>
    </html>
    """
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    
    mock_client.get.return_value = mock_response
    
    return mock_client


@pytest.fixture
def mock_celery_task():
    """
    Fixture pour mocker les tâches Celery.
    
    Évite l'exécution réelle des tâches Celery pendant les tests.
    """
    with patch('app.services.crawling_service.crawl_land_task') as mock_task:
        mock_result = Mock()
        mock_result.id = "test-celery-task-id"
        mock_task.delay.return_value = mock_result
        yield mock_task


@pytest.fixture
def mock_websocket_manager():
    """
    Fixture pour mocker le WebSocket manager.
    
    Simule les messages WebSocket sans connexions réelles.
    """
    with patch('app.core.websocket.websocket_manager') as mock_manager:
        mock_manager.broadcast_to_channel = AsyncMock()
        yield mock_manager


@pytest.fixture
def authenticated_client(test_user: User) -> TestClient:
    """
    Fixture pour créer un client de test FastAPI avec un utilisateur authentifié.
    
    Remplace la dépendance get_current_user pour simuler un utilisateur connecté.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def authenticated_admin_client(test_admin_user: User) -> TestClient:
    """
    Fixture pour créer un client de test FastAPI avec un utilisateur admin authentifié.
    """
    app.dependency_overrides[get_current_user] = lambda: test_admin_user
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


# Utilitaires pour les tests
class TestHelpers:
    """
    Classe utilitaire avec des méthodes d'aide pour les tests.
    """
    
    @staticmethod
    def create_mock_html_response(title: str = "Test", content: str = "Test content") -> str:
        """Crée une réponse HTML mock pour les tests."""
        return f"""
        <html>
            <head>
                <title>{title}</title>
                <meta name="description" content="Test description">
            </head>
            <body>
                <h1>{title}</h1>
                <p>{content}</p>
            </body>
        </html>
        """
    
    @staticmethod
    def create_mock_crawl_response(status_code: int = 200) -> dict:
        """Crée une réponse de crawl mock."""
        return {
            "status_code": status_code,
            "text": TestHelpers.create_mock_html_response(),
            "headers": {"content-type": "text/html"}
        }


@pytest.fixture
def test_helpers() -> TestHelpers:
    """Fixture pour accéder aux utilitaires de test."""
    return TestHelpers()
