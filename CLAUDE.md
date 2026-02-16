# CLAUDE.md - MyWebIntelligence Project Guide for AI Assistants

**Last Updated:** 2025-11-20
**Project Version:** 1.0.0
**Target Audience:** AI Assistants (Claude, GitHub Copilot, etc.)

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Repository Structure](#repository-structure)
3. [Architecture & Design Principles](#architecture--design-principles)
4. [Development Workflows](#development-workflows)
5. [Code Conventions](#code-conventions)
6. [Testing Guidelines](#testing-guidelines)
7. [Common Tasks & Commands](#common-tasks--commands)
8. [Database & Models](#database--models)
9. [API Structure](#api-structure)
10. [Important Files Reference](#important-files-reference)
11. [Troubleshooting](#troubleshooting)
12. [Do's and Don'ts](#dos-and-donts)

---

## 🎯 Project Overview

### What is MyWebIntelligence?

MyWebIntelligence is a **web crawling and content analysis platform** consisting of two main components in a state of transition:

1. **MyWebIntelligenceAPI** (Primary/Active): Modern FastAPI backend with PostgreSQL, Redis, and Celery for distributed crawling, content extraction, media analysis, and NLP processing.

2. **MyWebClient** (Legacy): React + Node.js frontend that operates on a separate SQLite database, scheduled for future migration to the new API.

### Technology Stack

**Backend (MyWebIntelligenceAPI):**
- **Framework:** FastAPI 0.104.1 + Uvicorn (ASGI server)
- **Database:** PostgreSQL 15 with SQLAlchemy 2.0.23 (async ORM)
- **Task Queue:** Celery with Redis broker
- **Caching:** Redis 7
- **Containerization:** Docker + Docker Compose
- **Testing:** Pytest with asyncio support
- **Content Extraction:** BeautifulSoup4, Trafilatura, Newspaper3k, Readability-lxml
- **Media Processing:** Pillow, ImageHash, ColorThief, ExifRead
- **NLP:** TextBlob, NLTK, LangDetect
- **LLM Integration:** OpenRouter API (for validation & sentiment)
- **Dynamic Scraping:** Playwright

**Frontend (Legacy):**
- React + Express.js + SQLite3 + Yarn

### Project Purpose

- Crawl domains with configurable depth and scope
- Extract and analyze content (text, metadata, media)
- Perform NLP analysis (sentiment, language detection, quality scoring)
- Export data in multiple formats (GEXF, JSON, CSV)
- Provide REST API for web intelligence operations

---

## 📁 Repository Structure

```
/home/user/mywebapi/
├── MyWebIntelligenceAPI/          # 🎯 PRIMARY: Modern FastAPI backend
│   ├── app/                       # Application source code
│   │   ├── main.py                # FastAPI entry point (startup, middleware, routes)
│   │   ├── config.py              # Pydantic settings (env vars)
│   │   ├── api/                   # REST API endpoints
│   │   │   ├── v1/                # Stable API v1 (auth, lands, domains, etc.)
│   │   │   ├── v2/                # Simplified sync-focused v2
│   │   │   ├── router.py          # Main v1 router
│   │   │   └── versioning.py      # API versioning middleware
│   │   ├── core/                  # Core business logic (crawlers, extractors)
│   │   │   ├── crawler_engine.py  # Main crawler (sync, ~45KB)
│   │   │   ├── content_extractor.py
│   │   │   ├── media_processor.py
│   │   │   ├── sentiment_provider.py
│   │   │   ├── celery_app.py      # Celery configuration
│   │   │   └── security.py        # JWT authentication
│   │   ├── services/              # High-level service layer
│   │   │   ├── crawling_service.py
│   │   │   ├── export_service.py
│   │   │   ├── quality_scorer.py
│   │   │   ├── llm_validation_service.py
│   │   │   └── sentiment_service.py
│   │   ├── db/                    # Database layer
│   │   │   ├── models.py          # SQLAlchemy ORM models
│   │   │   ├── schemas.py         # Pydantic request/response schemas
│   │   │   ├── session.py         # Database session management
│   │   │   └── base.py            # Base configurations
│   │   ├── crud/                  # Database CRUD operations
│   │   ├── tasks/                 # Celery async tasks
│   │   │   ├── crawling_task.py
│   │   │   ├── domain_crawl_task.py
│   │   │   └── export_tasks.py
│   │   └── utils/                 # Utilities
│   ├── tests/                     # Comprehensive test suite
│   │   ├── unit/                  # Unit tests (15+ files)
│   │   ├── integration/           # Integration tests
│   │   ├── legacy/                # Legacy API compatibility tests
│   │   ├── manual/                # Manual test scripts
│   │   └── conftest.py            # Pytest fixtures
│   ├── projetV3/                  # ⚠️ EXPERIMENTAL: Async/parallel version
│   │   ├── app/                   # V3 async implementations
│   │   ├── docs/                  # V3 technical documentation
│   │   └── tests/                 # V3-specific tests
│   ├── _legacy/                   # Deprecated code (do not use)
│   ├── migrations/                # Alembic database migrations
│   ├── scripts/                   # Utility scripts
│   ├── Dockerfile                 # Container definition
│   ├── requirements.txt           # Python dependencies (84 packages)
│   ├── .env.example              # Environment template
│   ├── pytest.ini                # Pytest configuration
│   └── README.md                 # API documentation
│
├── MyWebClient/                   # LEGACY: React frontend (scheduled for migration)
│   ├── client/                    # React app
│   ├── server/                    # Express backend
│   └── README.md
│
├── docker-compose.yml             # Service orchestration (API only)
├── README.md                      # Project root documentation
├── .claude/                       # Claude-specific documentation
│   ├── AGENTS.md
│   ├── INDEX_DOCUMENTATION.md
│   ├── INDEX_TESTS.md
│   └── V2_SIMPLIFICATION_SUMMARY.md
└── CLAUDE.md                      # This file
```

### Key Directories to Know

| Directory | Purpose | When to Use |
|-----------|---------|-------------|
| `app/api/v1/` | Stable API endpoints | Adding new features, bug fixes |
| `app/api/v2/` | Simplified sync API | New simplified sync endpoints |
| `app/core/` | Core crawling logic | Modifying crawler behavior |
| `app/services/` | Business logic | High-level feature implementation |
| `app/db/models.py` | Database schema | Adding/modifying tables |
| `app/db/schemas.py` | API schemas | Request/response validation |
| `tests/unit/` | Unit tests | Testing isolated components |
| `tests/integration/` | Integration tests | Testing full workflows |
| `projetV3/` | Experimental async | **Avoid unless explicitly working on V3** |
| `_legacy/` | Deprecated code | **Never use - for reference only** |

---

## 🏗️ Architecture & Design Principles

### Current Architecture (V2 - Stable)

**Design Philosophy:** Simplicity and stability over premature optimization

```
┌─────────────────┐
│   FastAPI App   │ ← HTTP Requests
│   (Uvicorn)     │
└────────┬────────┘
         │
         ├──→ PostgreSQL (persistent data)
         ├──→ Redis (caching, Celery broker)
         │
         v
┌─────────────────┐
│ Celery Workers  │ ← Async background tasks
│   (crawling)    │
└─────────────────┘
```

**Request Flow for Crawling:**
1. Client sends crawl request to API endpoint
2. API creates job record in PostgreSQL
3. API dispatches task to Celery queue (via Redis)
4. Celery worker picks up task
5. Worker executes **synchronous** crawler (CrawlerEngine)
6. Results saved to PostgreSQL
7. Job status updated to "completed"
8. Client polls job endpoint for status

### V2 Simplification (October 2025)

**Important:** The project underwent a major simplification in October 2025 to improve stability:

- **Removed:** Async/parallel HTTP crawling, WebSocket monitoring, embeddings, complex fallback chains
- **Kept:** Sync crawling via Celery, quality scoring, sentiment analysis, export functionality
- **Moved to projetV3:** All async/parallel code (~1500 lines)

**Why:** Async complexity created bugs (greenlet_spawn, session conflicts) without sufficient value for most use cases. V2 is now 33% smaller and significantly more stable.

**Performance Trade-off:** V2 crawls sequentially (~30s for 5 URLs) vs V1 async (~10s), but with zero async bugs.

### API Versioning

- **v1** (`/api/v1/`): Original stable API with full features
- **v2** (`/api/v2/`): Simplified sync-only version
- **v3** (experimental): In `projetV3/`, not exposed in main app

**Versioning Strategy:** Clients specify API version via:
- URL path (`/api/v1/lands` vs `/api/v2/lands`)
- Header: `API-Version: 2.0` (optional, middleware-based)

### Design Patterns Used

1. **Service Layer Pattern:** Business logic in `services/`, keeping API endpoints thin
2. **Repository Pattern:** CRUD operations in `crud/`, abstracting database access
3. **Factory Pattern:** Test fixtures use `factory-boy` for object creation
4. **Dependency Injection:** FastAPI's `Depends()` for database sessions, auth
5. **Task Queue Pattern:** Long-running operations delegated to Celery

---

## 🔧 Development Workflows

### Initial Setup

**Prerequisites:**
- Docker & Docker Compose (recommended)
- OR: Python 3.11+, PostgreSQL 15, Redis 7 (for local dev)

**Quick Start with Docker:**

```bash
# 1. Clone repository (already done)
cd /home/user/mywebapi

# 2. Configure environment
cp MyWebIntelligenceAPI/.env.example MyWebIntelligenceAPI/.env
# Edit .env: Set SECRET_KEY, API keys, etc.

# 3. Start services
docker-compose up -d

# 4. Verify services
curl http://localhost:8000  # API health check
curl http://localhost:8000/docs  # Swagger UI
```

**Services Started:**
- `db`: PostgreSQL on internal network
- `redis`: Redis on internal network
- `mywebintelligenceapi`: API on port 8000
- `celery_worker`: Background task processor

### Local Development (Without Docker)

```bash
cd MyWebIntelligenceAPI

# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env for local PostgreSQL/Redis
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mywebdb

# 4. Run migrations (if using Alembic)
# alembic upgrade head

# 5. Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. In another terminal, start Celery worker
celery -A app.core.celery_app worker --loglevel=info
```

### Git Workflow

**Branch Strategy:**
- `main`: Production-ready code (not directly committed to)
- `claude/*`: Feature branches created by Claude
- Feature branches: Named descriptively

**Typical Workflow:**
```bash
# 1. Create feature branch
git checkout -b feature/add-new-feature

# 2. Make changes, run tests
pytest MyWebIntelligenceAPI/tests/

# 3. Commit with descriptive message
git add .
git commit -m "Add feature: description of what and why"

# 4. Push to remote
git push -u origin feature/add-new-feature

# 5. Create pull request (manual or via gh CLI)
```

**Commit Message Style (inferred from git log):**
- Start with action verb: `fix:`, `feat:`, `refactor:`, `docs:`
- Brief description of what changed
- Focus on "why" in commit body if needed
- Examples:
  - `fix: Final import cleanups for V2 simplification`
  - `Refactor: Simplify V2 to sync-only, move async code to projetV3`

### Running Tests

**Full Test Suite:**
```bash
cd MyWebIntelligenceAPI
pytest
```

**Specific Test Categories:**
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_quality_scorer.py

# With coverage report
pytest --cov=app --cov-report=html

# Run async tests
pytest tests/integration/test_crawl_workflow_integration.py -v
```

**Manual Test Scripts:**
```bash
# Simple crawl test
./tests/test-crawl-simple.sh

# Domain crawl test
./tests/test-domain-crawl.sh

# LLM validation test
./tests/test-llm-validation.sh
```

### Building & Deployment

**Docker Build:**
```bash
# Build API image
docker-compose build mywebintelligenceapi

# Rebuild and restart services
docker-compose up -d --build
```

**Production Checklist:**
1. Set `DEBUG=False` in `.env`
2. Set strong `SECRET_KEY`
3. Configure production database credentials
4. Set `CELERY_AUTOSCALE` for worker scaling
5. Enable `ENABLE_PROMETHEUS=True` for monitoring
6. Review CORS origins in `BACKEND_CORS_ORIGINS`
7. Set API keys for external services (OpenRouter, SerpAPI, etc.)

---

## 📝 Code Conventions

### Language & Style

**Primary Language:** Python 3.11+

**Code Style:**
- Follow PEP 8
- Use type hints extensively (Python `typing` module)
- Prefer async/await in V3, sync in V2 (after simplification)
- Maximum line length: 100-120 characters (not strictly enforced)

**Naming Conventions:**
- **Functions/Variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private methods:** `_leading_underscore`
- **Database models:** `PascalCase` (e.g., `Land`, `Domain`, `Expression`)
- **API endpoints:** `kebab-case` in URLs, `snake_case` in Python

**Example:**
```python
# Good
class CrawlerEngine:
    def __init__(self, max_depth: int):
        self.max_depth = max_depth
        self._visited_urls: Set[str] = set()

    async def crawl_url(self, url: str) -> CrawlResult:
        """Crawl a single URL and extract content."""
        ...

# API endpoint
@router.get("/lands/{land_id}", response_model=LandResponse)
async def get_land(land_id: int, db: AsyncSession = Depends(get_db)):
    ...
```

### Documentation Style

**Docstrings:** Mixed French/English (historical reasons)
- Module-level docstrings: Brief description in French
- Function docstrings: Parameters and return types
- Complex logic: Inline comments explaining "why"

**Example:**
```python
"""
Service de crawling synchrone pour V2
"""

def crawl_domain(domain_url: str, max_depth: int = 3) -> Dict[str, Any]:
    """
    Crawl un domaine de manière synchrone.

    Args:
        domain_url: URL du domaine à crawler
        max_depth: Profondeur maximale de crawling

    Returns:
        Dict contenant les expressions extraites et les statistiques
    """
    # Initialiser le crawler avec timeout configuré
    crawler = CrawlerEngine(timeout=settings.CRAWL_TIMEOUT)
    ...
```

### Import Organization

**Order:**
1. Standard library imports
2. Third-party imports (alphabetical)
3. Local application imports (alphabetical)

**Example:**
```python
# Standard library
import logging
from typing import List, Dict, Optional

# Third-party
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Local
from app.config import settings
from app.db.session import get_db
from app.db.schemas import LandCreate, LandResponse
from app.services.crawling_service import CrawlingService
```

### Error Handling

**Patterns:**
- Use FastAPI's `HTTPException` for API errors
- Log errors with appropriate levels (ERROR, WARNING, INFO)
- Provide user-friendly error messages
- Include error context for debugging

**Example:**
```python
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

async def get_land_by_id(land_id: int, db: AsyncSession) -> Land:
    try:
        result = await db.execute(select(Land).where(Land.id == land_id))
        land = result.scalar_one_or_none()

        if not land:
            raise HTTPException(
                status_code=404,
                detail=f"Land with id {land_id} not found"
            )

        return land
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching land {land_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

### Configuration Management

**All configuration via environment variables:**
- Defined in `.env` file (gitignored)
- Loaded via `app/config.py` using Pydantic `BaseSettings`
- Type-safe with defaults

**Never hardcode:**
- API keys
- Database credentials
- Secret keys
- Feature flags

**Example:**
```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "MyWebIntelligence API"
    DEBUG: bool = False
    DATABASE_URL: str
    SECRET_KEY: str
    OPENROUTER_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 🧪 Testing Guidelines

### Test Structure

**Pytest Configuration:** `pytest.ini` sets `asyncio_mode = auto` for async tests

**Test Organization:**
```
tests/
├── conftest.py           # Shared fixtures (db session, factories)
├── unit/                 # Fast, isolated tests (~15 files)
│   ├── test_quality_scorer.py
│   ├── test_llm_validation_service.py
│   └── api/v1/test_auth.py
├── integration/          # Full workflow tests
│   ├── test_crawl_workflow_integration.py
│   └── test_export_integration.py
├── legacy/               # Tests for legacy API compatibility
└── manual/               # Scripts for manual testing
```

### Writing Tests

**Unit Test Pattern:**
```python
import pytest
from app.services.quality_scorer import QualityScorer

class TestQualityScorer:
    def test_score_high_quality_content(self):
        """Test that high-quality content gets high score"""
        scorer = QualityScorer()
        content = "This is a well-written article with plenty of detail." * 20

        score = scorer.calculate_score(
            content=content,
            word_count=200,
            has_images=True
        )

        assert score > 0.7
        assert 0 <= score <= 1.0

    def test_score_low_quality_content(self):
        """Test that low-quality content gets low score"""
        scorer = QualityScorer()
        content = "Short."

        score = scorer.calculate_score(content=content, word_count=1)

        assert score < 0.3
```

**Integration Test Pattern (Async):**
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_crawl_workflow(async_client: AsyncClient, db_session):
    """Test full crawl workflow from API request to completion"""
    # Create land
    land_data = {
        "title": "Test Land",
        "seed_urls": ["https://example.com"]
    }
    response = await async_client.post("/api/v1/lands/", json=land_data)
    assert response.status_code == 201
    land_id = response.json()["id"]

    # Start crawl
    crawl_data = {"land_id": land_id, "max_depth": 2}
    response = await async_client.post("/api/v1/jobs/crawl", json=crawl_data)
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Poll for completion (simplified)
    # ... (check job status, verify expressions created)
```

**Fixtures (conftest.py):**
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def db_session():
    """Provide database session for tests"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def async_client():
    """Provide async HTTP client for API tests"""
    return AsyncClient(app=app, base_url="http://test")
```

### Test Coverage Goals

- **Critical paths:** 100% coverage (crawling, authentication, data export)
- **Business logic:** >80% coverage (services, quality scoring)
- **API endpoints:** >70% coverage
- **Overall:** >70% coverage

**Check coverage:**
```bash
pytest --cov=app --cov-report=term-missing
```

### Testing Best Practices

1. **Test one thing per test:** Clear failure messages
2. **Use descriptive test names:** `test_should_return_404_when_land_not_found`
3. **Arrange-Act-Assert pattern:**
   ```python
   # Arrange
   land = create_test_land()

   # Act
   result = service.delete_land(land.id)

   # Assert
   assert result.success is True
   ```
4. **Mock external dependencies:** Use `pytest-mock` for API calls, file I/O
5. **Use factories for test data:** `factory-boy` for complex objects
6. **Clean up after tests:** Use fixtures with teardown or `yield`

---

## 🗄️ Database & Models

### Database Schema Overview

**ORM:** SQLAlchemy 2.0 with async support (`asyncpg` driver)

**Core Tables:**

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | Authentication | id, email, hashed_password, is_superuser |
| `lands` | Crawl projects | id, title, seed_urls, user_id, status |
| `domains` | Website records | id, url, land_id, status, last_crawled_at |
| `expressions` | Extracted content | id, domain_id, url, title, content, sentiment_score |
| `paragraphs` | Content units | id, expression_id, text, relevance, sentiment |
| `tags` | Categorization | id, name, color |
| `expression_tags` | Many-to-many | expression_id, tag_id |
| `media` | Images/files | id, expression_id, url, media_type, dominant_color |
| `jobs` | Background tasks | id, land_id, job_type, status, progress |
| `dictionaries` | Keyword lists | id, land_id, words (JSON array) |

### Model Conventions

**File:** `app/db/models.py`

**Pattern:**
- Table name: lowercase plural (e.g., `lands`, `expressions`)
- Primary key: `id` (Integer, autoincrement)
- Timestamps: `created_at`, `updated_at` (DateTime with timezone)
- Foreign keys: `{table}_id` (e.g., `land_id`, `user_id`)
- Relationships: Use `relationship()` for ORM navigation

**Example:**
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Land(Base):
    __tablename__ = "lands"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    seed_urls = Column(JSON)  # List of starting URLs
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="active")  # active, archived, deleted
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="lands")
    domains = relationship("Domain", back_populates="land", cascade="all, delete-orphan")
```

### Schema Conventions (Pydantic)

**File:** `app/db/schemas.py`

**Pattern:**
- `{Model}Base`: Shared fields
- `{Model}Create`: Fields for creation (POST)
- `{Model}Update`: Fields for updates (PUT/PATCH)
- `{Model}Response`: Fields for responses (GET)
- `{Model}InDB`: Fields stored in database (internal)

**Example:**
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class LandBase(BaseModel):
    title: str
    seed_urls: List[str]

class LandCreate(LandBase):
    """Schema for creating a land"""
    pass

class LandUpdate(BaseModel):
    """Schema for updating a land (all fields optional)"""
    title: Optional[str] = None
    seed_urls: Optional[List[str]] = None
    status: Optional[str] = None

class LandResponse(LandBase):
    """Schema for land responses"""
    id: int
    user_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode
```

### Database Sessions

**Pattern:** Async session via dependency injection

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db.session import get_db

@router.get("/lands/{land_id}")
async def get_land(
    land_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Land).where(Land.id == land_id))
    land = result.scalar_one_or_none()
    return land
```

**Important:**
- Always use `async with` or dependency injection for sessions
- Commit explicitly: `await db.commit()`
- Refresh after commit to get updated fields: `await db.refresh(obj)`

### Migrations

**Tool:** Alembic (configured but migrations stored in `migrations/versions/`)

**Note:** Currently, migrations are auto-applied on startup via `main.py`:
```python
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**For explicit migrations:**
```bash
# Create migration
alembic revision --autogenerate -m "Add new field to expressions"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🌐 API Structure

### Endpoint Organization

**Base URLs:**
- API v1: `http://localhost:8000/api/v1/`
- API v2: `http://localhost:8000/api/v2/`
- Docs: `http://localhost:8000/docs` (Swagger UI)
- ReDoc: `http://localhost:8000/redoc`

### API v1 Endpoints

**Authentication (`/api/v1/auth/`):**
- `POST /login` - Login with email/password, returns JWT
- `POST /register` - Register new user
- `POST /token/refresh` - Refresh access token

**Lands (`/api/v1/lands/`):**
- `GET /` - List all lands (paginated)
- `POST /` - Create new land
- `GET /{land_id}` - Get land by ID
- `PUT /{land_id}` - Update land
- `DELETE /{land_id}` - Delete land
- `GET /{land_id}/stats` - Get land statistics

**Domains (`/api/v1/domains/`):**
- `GET /` - List domains (filterable by land_id)
- `POST /` - Create domain
- `GET /{domain_id}` - Get domain by ID
- `PUT /{domain_id}` - Update domain
- `DELETE /{domain_id}` - Delete domain

**Expressions (`/api/v1/expressions/`):**
- `GET /` - List expressions (filterable by domain_id, land_id)
- `GET /{expression_id}` - Get expression by ID
- `PUT /{expression_id}` - Update expression
- `DELETE /{expression_id}` - Delete expression

**Jobs (`/api/v1/jobs/`):**
- `POST /crawl` - Start crawl job
- `GET /{job_id}` - Get job status
- `GET /` - List jobs

**Export (`/api/v1/export/`):**
- `POST /gexf` - Export land as GEXF graph
- `POST /json` - Export land as JSON
- `POST /csv` - Export land as CSV

**Tags, Paragraphs, Dictionaries:** Similar CRUD patterns

### API v2 Differences

**Simplified focus:**
- Removed: Async crawl options, WebSocket endpoints
- Kept: Core CRUD, sync crawling via Celery
- Same auth mechanism

### API Response Conventions

**Success Responses:**
```json
{
  "id": 123,
  "title": "My Land",
  "created_at": "2025-11-20T10:30:00Z",
  "status": "active"
}
```

**Error Responses:**
```json
{
  "detail": "Land with id 999 not found"
}
```

**List Responses (if paginated):**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 20
}
```

### Authentication

**Method:** JWT (JSON Web Tokens)

**Flow:**
1. Client sends credentials to `/api/v1/auth/login`
2. Server returns `access_token` (30 min expiry) and `refresh_token` (7 days)
3. Client includes token in requests: `Authorization: Bearer <token>`
4. Server validates token via dependency: `current_user = Depends(get_current_user)`

**Protected Endpoints:**
```python
from app.core.security import get_current_user

@router.get("/lands/")
async def list_lands(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # User is authenticated, current_user is available
    return await land_service.get_user_lands(user_id=current_user.id, db=db)
```

---

## 📚 Important Files Reference

### Configuration Files

| File | Purpose | When to Edit |
|------|---------|--------------|
| `.env.example` | Environment template | Adding new config options |
| `.env` | Runtime config (gitignored) | Local development setup |
| `pytest.ini` | Pytest configuration | Changing test behavior |
| `requirements.txt` | Python dependencies | Adding new packages |
| `docker-compose.yml` | Service orchestration | Changing services/ports |
| `Dockerfile` | Container definition | Changing build process |

### Key Source Files

| File | Purpose | Modify When |
|------|---------|-------------|
| `app/main.py` | FastAPI app entry point | Adding middleware, startup logic |
| `app/config.py` | Settings management | Adding configuration options |
| `app/core/crawler_engine.py` | Core crawler logic | Changing crawl behavior |
| `app/core/content_extractor.py` | Content extraction | Improving extraction quality |
| `app/services/crawling_service.py` | Crawl orchestration | High-level crawl workflow changes |
| `app/services/quality_scorer.py` | Content quality algorithm | Adjusting quality metrics |
| `app/db/models.py` | Database schema | Adding/modifying tables |
| `app/db/schemas.py` | API request/response schemas | Adding/modifying API fields |

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview, installation |
| `MyWebIntelligenceAPI/README.md` | API-specific documentation |
| `.claude/V2_SIMPLIFICATION_SUMMARY.md` | V2 refactoring details |
| `.claude/AGENTS.md` | AI agent configurations |
| `projetV3/README.md` | V3 experimental documentation |

---

## 🛠️ Common Tasks & Commands

### Starting the Application

**Docker (Recommended):**
```bash
docker-compose up -d              # Start all services
docker-compose logs -f api        # View API logs
docker-compose logs -f celery_worker  # View Celery logs
docker-compose down               # Stop all services
docker-compose restart api        # Restart API only
```

**Local:**
```bash
# Terminal 1: API server
cd MyWebIntelligenceAPI
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: Celery worker
celery -A app.core.celery_app worker --loglevel=info
```

### Database Operations

**View database in Docker:**
```bash
docker-compose exec db psql -U mwi_user -d mwi_db
```

**Common SQL queries:**
```sql
-- List all lands
SELECT id, title, status, created_at FROM lands;

-- Count expressions per land
SELECT land_id, COUNT(*) FROM expressions GROUP BY land_id;

-- Recent crawl jobs
SELECT id, land_id, job_type, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 10;
```

**Reset database (Docker):**
```bash
docker-compose down -v  # Remove volumes (WARNING: deletes all data)
docker-compose up -d
```

### Debugging

**Check API health:**
```bash
curl http://localhost:8000/
curl http://localhost:8000/docs  # Should return HTML
```

**Check Celery connection:**
```bash
docker-compose exec celery_worker celery -A app.core.celery_app inspect active
```

**Check Redis:**
```bash
docker-compose exec redis redis-cli ping  # Should return PONG
```

**View logs:**
```bash
docker-compose logs -f --tail=100 api
docker-compose logs -f --tail=100 celery_worker
```

### Running Specific Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Specific test file
pytest tests/unit/test_quality_scorer.py -v

# Specific test function
pytest tests/unit/test_quality_scorer.py::TestQualityScorer::test_high_quality -v

# With print output
pytest tests/unit/test_quality_scorer.py -v -s

# Skip slow tests
pytest -m "not slow"
```

### Code Quality Checks

```bash
# Linting (if configured)
flake8 app/

# Type checking (if mypy installed)
mypy app/

# Format code (if black installed)
black app/

# Sort imports (if isort installed)
isort app/
```

### Creating New Endpoints

**1. Define schema in `app/db/schemas.py`:**
```python
class NewFeatureCreate(BaseModel):
    name: str
    value: int

class NewFeatureResponse(BaseModel):
    id: int
    name: str
    value: int
    created_at: datetime

    class Config:
        from_attributes = True
```

**2. Create router in `app/api/v1/new_feature.py`:**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.schemas import NewFeatureCreate, NewFeatureResponse

router = APIRouter()

@router.post("/", response_model=NewFeatureResponse)
async def create_feature(
    data: NewFeatureCreate,
    db: AsyncSession = Depends(get_db)
):
    # Implementation
    ...
```

**3. Register router in `app/api/router.py`:**
```python
from app.api.v1 import new_feature

api_router.include_router(
    new_feature.router,
    prefix="/new-feature",
    tags=["new-feature"]
)
```

**4. Write tests in `tests/unit/api/v1/test_new_feature.py`**

**5. Test manually via Swagger UI at `/docs`**

---

## 🚨 Troubleshooting

### Common Issues

**Issue: "ModuleNotFoundError: No module named 'app'"**
- **Cause:** Running Python from wrong directory
- **Solution:** Always run from `MyWebIntelligenceAPI/` directory or ensure PYTHONPATH includes it

**Issue: "asyncpg.exceptions.InvalidCatalogNameError: database does not exist"**
- **Cause:** PostgreSQL database not created
- **Solution:** Database should auto-create in Docker. For local dev, create manually:
  ```bash
  createdb -U postgres mywebintelligence
  ```

**Issue: "Connection refused" when connecting to Redis/PostgreSQL**
- **Cause:** Services not running or wrong connection string
- **Solution:**
  - Check `docker-compose ps` to verify services are up
  - Verify `.env` has correct DATABASE_URL and REDIS_URL
  - In Docker: use service names (`redis`, `db`), not `localhost`

**Issue: Celery tasks not executing**
- **Cause:** Celery worker not running or misconfigured broker
- **Solution:**
  - Check `docker-compose logs celery_worker`
  - Verify CELERY_BROKER_URL points to Redis
  - Ensure tasks are registered in `celery_app.py`

**Issue: "greenlet_spawn" errors in logs (V3 async code)**
- **Cause:** Async/sync mixing in SQLAlchemy operations
- **Solution:** This is a known V3 issue. Stick to V2 sync code for stability.

**Issue: Tests failing with "event loop is closed"**
- **Cause:** Async test cleanup issues
- **Solution:** Ensure `pytest.ini` has `asyncio_mode = auto`

**Issue: Import errors after moving files**
- **Cause:** Python cache not cleared
- **Solution:**
  ```bash
  find . -type d -name "__pycache__" -exec rm -r {} +
  find . -type f -name "*.pyc" -delete
  ```

### Performance Issues

**Slow crawling:**
- Check `CRAWL_TIMEOUT` in `.env` (default: 30s per page)
- Reduce `CRAWL_MAX_DEPTH` for faster results
- Verify network connectivity to target sites

**High memory usage:**
- Reduce `CELERY_AUTOSCALE` max workers
- Check for memory leaks in custom code
- Monitor with Prometheus if enabled

**Database query slowness:**
- Add indexes to frequently queried fields
- Use `select()` with specific columns, not `SELECT *`
- Check `docker-compose logs db` for slow query logs

---

## ✅ Do's and Don'ts

### DO:

✅ **Use V2 API for new features** - It's stable and actively maintained
✅ **Write tests for new code** - Especially for crawling and data processing logic
✅ **Use type hints** - Helps catch bugs early and improves IDE support
✅ **Log important operations** - Use appropriate levels (INFO, WARNING, ERROR)
✅ **Use environment variables** - Never hardcode credentials or API keys
✅ **Follow existing patterns** - Service layer, CRUD separation, dependency injection
✅ **Read `.claude/V2_SIMPLIFICATION_SUMMARY.md`** - Understand recent architectural decisions
✅ **Test with manual scripts** - Use `tests/*.sh` for integration testing
✅ **Use async/await correctly** - In V2, prefer sync with Celery; in V3, use async patterns
✅ **Document complex logic** - Especially algorithms like quality scoring
✅ **Check git history** - Use `git log` to understand why code changed

### DON'T:

❌ **Don't use code from `_legacy/` directory** - It's deprecated and unmaintained
❌ **Don't modify `projetV3/` unless explicitly working on V3** - It's experimental
❌ **Don't mix async/sync SQLAlchemy operations** - Causes greenlet errors
❌ **Don't commit `.env` file** - Contains secrets, is gitignored
❌ **Don't bypass authentication** - Always use `get_current_user` dependency
❌ **Don't write synchronous code in async functions** - Use `run_in_executor` if needed
❌ **Don't ignore test failures** - Fix or understand why they fail
❌ **Don't use `SELECT *` queries** - Be explicit about needed columns
❌ **Don't add large dependencies without discussion** - Keep `requirements.txt` lean
❌ **Don't skip database migrations** - Use Alembic for schema changes
❌ **Don't expose internal errors to API clients** - Wrap in generic HTTP exceptions
❌ **Don't use WebSocket endpoints in V2** - They were removed in simplification

### When Adding New Features:

1. ✅ Check if it belongs in V1, V2, or V3
2. ✅ Start with tests (TDD approach)
3. ✅ Add to appropriate service layer first
4. ✅ Create API endpoint thin, delegate to service
5. ✅ Update schemas for request/response validation
6. ✅ Document in docstrings and update this file if major
7. ✅ Test via Swagger UI before committing
8. ✅ Run full test suite: `pytest`
9. ✅ Update `.env.example` if adding config options

### When Fixing Bugs:

1. ✅ Write a failing test that reproduces the bug
2. ✅ Fix the code to make the test pass
3. ✅ Verify no other tests broke
4. ✅ Check if bug exists in other versions (V1, V2, V3)
5. ✅ Add regression test to prevent future recurrence

---

## 🎓 Additional Resources

### Internal Documentation

- **Architecture Overview:** `.claude/system/Architecture.md` (if exists)
- **Test Index:** `.claude/INDEX_TESTS.md`
- **Documentation Index:** `.claude/INDEX_DOCUMENTATION.md`
- **V3 Async Details:** `projetV3/README.md`

### External References

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0:** https://docs.sqlalchemy.org/en/20/
- **Celery:** https://docs.celeryq.dev/
- **Pydantic:** https://docs.pydantic.dev/
- **Pytest:** https://docs.pytest.org/

### Code Examples

**Typical Service Method:**
```python
# app/services/example_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class ExampleService:
    async def get_items(self, db: AsyncSession, user_id: int):
        result = await db.execute(
            select(Item).where(Item.user_id == user_id)
        )
        return result.scalars().all()
```

**Typical API Endpoint:**
```python
# app/api/v1/example.py
from fastapi import APIRouter, Depends
from app.core.security import get_current_user

router = APIRouter()

@router.get("/items/", response_model=List[ItemResponse])
async def list_items(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ExampleService()
    return await service.get_items(db, user_id=current_user.id)
```

**Typical Celery Task:**
```python
# app/tasks/example_task.py
from app.core.celery_app import celery_app

@celery_app.task
def process_item(item_id: int):
    # Long-running task
    result = do_expensive_computation(item_id)
    return {"item_id": item_id, "result": result}
```

---

## 📞 Contact & Contribution

**Maintainer:** Équipe MyWebIntelligence

**For AI Assistants:**
- When uncertain about architectural decisions, consult `.claude/V2_SIMPLIFICATION_SUMMARY.md`
- For version-specific questions, check the appropriate README (V1: main README, V2: this file, V3: projetV3/README.md)
- When in doubt, prefer simplicity and stability (V2 philosophy)

**Git Workflow:**
- All changes should go through feature branches
- Commit messages should be clear and descriptive
- Run tests before pushing
- Use pull requests for code review (when applicable)

---

**Last Updated:** 2025-11-20
**Document Version:** 1.0.0
**Next Review:** When major architectural changes occur

---

*This document is maintained as part of the MyWebIntelligence project and should be updated when significant changes to the codebase structure, conventions, or workflows are made.*
