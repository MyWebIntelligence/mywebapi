import pytest
import asyncio
import time
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.main import app
from app.db.base import Base
from app.api.dependencies import get_db
from app.db.models import User, Land, CrawlJob as DBCrawlJob, CrawlStatus
from sqlalchemy import select
from app.core.security import create_access_token

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./tests/data/test.db"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
TestingSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Dependency override
async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def test_user():
    async with TestingSessionLocal() as session:
        user = User(
            email="test@example.com",
            hashed_password="hashedpassword",
            is_active=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

@pytest.fixture
async def test_land(test_user):
    async with TestingSessionLocal() as session:
        land = Land(
            name="Test Land",
            description="Test Description", 
            owner_id=test_user.id,
            start_urls=["http://example.com"],
            lang="en"
        )
        session.add(land)
        await session.commit()
        await session.refresh(land)
        return land

@pytest.fixture
def test_token(test_user):
    return create_access_token({"sub": test_user.email})

@pytest.mark.asyncio
async def test_full_crawl_workflow(client: AsyncClient, test_land, test_token):
    # Start crawl job
    response = await client.post(
        f"/api/v1/lands/{test_land.id}/crawl",
        headers={"Authorization": f"Bearer {test_token}"},
        json={"limit": 1, "depth": 0}
    )
    assert response.status_code == 200
    job_data = response.json()
    job_id = job_data["id"]
    
    # Poll for job completion
    timeout = 60  # 60 seconds timeout
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        await asyncio.sleep(2)
        async with TestingSessionLocal() as session:
            result = await session.execute(select(DBCrawlJob).where(DBCrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if job is not None and str(job.status) == "completed":
                break
            if job is not None and str(job.status) == "failed":
                pytest.fail(f"Crawl failed: {job.result_data}")
    
    # Verify job results
    async with TestingSessionLocal() as session:
        result = await session.execute(select(DBCrawlJob).where(DBCrawlJob.id == job_id))
        job = result.scalar_one_or_none()
        assert job is not None
        assert str(job.status) == "completed"
        result_data = job.result_data or {}
        assert isinstance(result_data, dict)
        assert "processed" in result_data
        assert result_data["processed"] > 0
