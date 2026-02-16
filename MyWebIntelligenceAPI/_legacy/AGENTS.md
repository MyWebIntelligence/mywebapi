# AGENTS.md

> **AI Coding Assistant Context Documentation**
> Comprehensive project reference for AI-powered CLI tools (Claude Code, Cline, Cursor, Copilot, etc.)

---

## Table of Contents

- [Project Identity](#project-identity)
- [Quick Start Commands](#quick-start-commands)
- [Architecture Overview](#architecture-overview)
- [Database Schema](#database-schema)
- [Core Workflows](#core-workflows)
- [Configuration Guide](#configuration-guide)
- [Development Guidelines](#development-guidelines)
- [Testing Strategy](#testing-strategy)
- [Export Capabilities](#export-capabilities)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Security & Permissions](#security--permissions)

---

## Project Identity

**Name:** MyWebIntelligence (MyWI)
**Type:** Python CLI application
**Purpose:** Web intelligence tool for digital humanities researchers
**Language:** Python 3.10+
**Framework:** Peewee ORM + SQLite
**Default Language:** French (configurable)

### What MyWI Does

- **Collect** web data through intelligent crawling
- **Organize** research into thematic "lands" (research projects)
- **Analyze** content with relevance scoring, media extraction, embeddings
- **Export** data in multiple formats (CSV, GEXF, corpus)

### Key Concepts

- **Land**: A thematic research collection (e.g., "AsthmaResearch", "ClimateChange")
- **Expression**: Individual web pages/URLs with metadata
- **Domain**: Unique websites encountered during crawling
- **Media**: Images, videos, audio extracted from pages
- **Embeddings**: Paragraph-level semantic vectors for similarity analysis
- **Pseudolinks**: Semantic relationships between paragraphs

---

## Quick Start Commands

### Database Initialization

```bash
# Create fresh database (DESTRUCTIVE)
python mywi.py db setup

# Update schema (safe, adds missing columns)
python mywi.py db migrate
```

### Land Management Workflow

```bash
# 1. Create a land
python mywi.py land create --name="MyTopic" --desc="Research description" --lang="fr"

# 2. Add keywords
python mywi.py land addterm --land="MyTopic" --terms="keyword1, keyword2, phrase"

# 3. Add seed URLs
python mywi.py land addurl --land="MyTopic" --urls="https://example.com, https://site.org"
# OR from file
python mywi.py land addurl --land="MyTopic" --path="/path/to/urls.txt"

# 4. Crawl URLs
python mywi.py land crawl --name="MyTopic" --limit=100

# 5. Extract readable content
python mywi.py land readable --name="MyTopic" --merge=smart_merge

# 6. Export results
python mywi.py land export --name="MyTopic" --type=pagecsv
```

### Testing Commands

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_cli.py

# Run specific test method
pytest tests/test_cli.py::test_functional_test
```

---

## Architecture Overview

### File Structure

```
mywi.py                        # Entry point
mwi/
├── __init__.py                # Package initialization
├── cli.py                     # Command-line interface parser (argparse)
├── controller.py              # Command → business logic mapping
│   ├── DbController           # Database operations (setup, migrate)
│   ├── LandController         # Land management (CRUD, crawl, export)
│   ├── DomainController       # Domain crawling operations
│   ├── TagController          # Tag export operations
│   ├── EmbeddingController    # Embeddings and similarity
│   └── HeuristicController    # Heuristic updates
├── core.py                    # Core algorithms (crawl, parse, score)
├── model.py                   # Database schema (Peewee ORM)
├── export.py                  # Data export functionality
│   ├── write_pagecsv()        # Page CSV export
│   ├── write_fullpagecsv()    # Full page CSV export
│   ├── write_nodecsv()        # Node CSV export
│   ├── write_mediacsv()       # Media CSV export
│   ├── write_pagegexf()       # Page GEXF graph export
│   ├── write_nodegexf()       # Node GEXF graph export
│   ├── write_pseudolinks()    # Paragraph similarity CSV
│   ├── write_pseudolinkspage() # Page-level aggregation CSV
│   ├── write_pseudolinksdomain() # Domain-level aggregation CSV
│   ├── write_corpus()         # Text corpus ZIP export
│   └── export_tags()          # Tag matrix/content export
├── media_analyzer.py          # Media analysis (images, videos, audio)
├── readable_pipeline.py       # Mercury Parser integration
├── embedding_pipeline.py      # Paragraph embeddings & similarity
├── semantic_pipeline.py       # ANN + NLI semantic relations (FAISS optional)
├── llm_openrouter.py          # OpenRouter LLM integration for validation
├── queries.py                 # (deprecated/removed module)
└── settings.py                # Configuration (created by install scripts)

scripts/                       # Helper scripts
├── install-basic.py           # Basic settings wizard
├── install-api.py             # API keys configuration
├── install-llm.py             # LLM/embeddings setup
├── docker-compose-setup.sh    # Docker automated setup
├── test-apis.py               # API validation
├── sqlite_recover.sh          # SQLite database recovery tool
├── crawl_robuste.sh           # Robust crawling with retry loop
└── install_utils.py           # Shared installer utilities

tests/                         # Test suite
├── test_cli.py                # CLI tests
├── test_core.py               # Core logic tests
├── test_metadata*.py          # Metadata extraction tests
└── test_expression_metadata.py
```

### Data Flow

```
User → CLI → Controller → Core/Export
                ↓
            Model (Peewee)
                ↓
            SQLite DB
```

### Key Design Patterns

- **MVC-like**: CLI (View) → Controller → Model/Core (Business Logic)
- **Async I/O**: Polite concurrent web crawling with aiohttp
- **ORM**: Peewee for database abstraction
- **Pipeline Pattern**: Modular processing (crawl → readable → analyze → export)
- **Controller Pattern**: Six specialized controllers handle different domains:
  - `DbController`: Database schema management
  - `LandController`: Research land operations (main controller)
  - `DomainController`: Domain-level operations
  - `TagController`: Tag export operations
  - `EmbeddingController`: Embeddings and semantic similarity
  - `HeuristicController`: Domain-specific URL pattern updates
- **Plugin Architecture**: Optional dependencies (Playwright, FAISS, sentence-transformers)

---

## Database Schema

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **Land** | Research projects | `name` (unique), `description`, `lang`, `created_at` |
| **Expression** | Individual URLs/pages | `url`, `title`, `content`, `relevance`, `fetched_at`, `http_status` |
| **ExpressionLink** | Links between pages | `source_id`, `target_id`, `link_text` |
| **Domain** | Unique websites | `name`, `title`, `description`, `fetched_at` |
| **Word** | Normalized vocabulary | `value` (lemmatized), `lang` |
| **LandDictionary** | Many-to-many Land↔Word | `land_id`, `word_id` |
| **Media** | Extracted media files | `url`, `type`, `dimensions`, `colors`, `hash` |
| **Tag** | Hierarchical tags | `path`, `name` |
| **TaggedContent** | Tagged content snippets | `expression_id`, `tag_id`, `content` |

### Embeddings & Similarity Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **Paragraph** | Text chunks from pages | `expression_id`, `paragraph_index`, `content` |
| **ParagraphEmbedding** | Vector representations | `paragraph_id`, `vector` (JSON), `model_name` |
| **ParagraphSimilarity** | Semantic links | `source_id`, `target_id`, `score`, `score_raw`, `relation_score` |

### Expression Extended Fields

- `validllm`: OpenRouter verdict ("oui"/"non")
- `validmodel`: Model used for validation
- `seorank`: Raw SEO Rank API JSON payload
- `readable`: Clean extracted text (Mercury Parser)

---

## Core Workflows

### 1. Project Bootstrap

```bash
# Fresh start
python mywi.py db setup

# Upgrade existing DB
python mywi.py db migrate
```

### 2. Land Lifecycle

```bash
# Create
python mywi.py land create --name="MyResearch" --desc="Description"

# List all
python mywi.py land list

# Show specific
python mywi.py land list --name="MyResearch"

# Delete (careful!)
python mywi.py land delete --name="MyResearch"

# Delete low-relevance only
python mywi.py land delete --name="MyResearch" --maxrel=0.5
```

### 3. Data Collection

```bash
# Bootstrap from Google (requires SerpAPI key)
python mywi.py land urlist --name="MyResearch" \
  --query="(climate change) OR (global warming)" \
  --datestart=2023-01-01 --dateend=2023-12-31 --timestep=week

# Crawl URLs
python mywi.py land crawl --name="MyResearch" --limit=100 --depth=2

# Re-crawl errors
python mywi.py land crawl --name="MyResearch" --http=503

# Extract readable content
python mywi.py land readable --name="MyResearch" --merge=smart_merge

# SEO metrics (requires SEO Rank API key)
python mywi.py land seorank --name="MyResearch" --limit=100 --depth=0
```

### 4. Media Analysis

```bash
# Analyze media in land
python mywi.py land medianalyse --name="MyResearch" --depth=2 --minrel=0.5
```

### 5. Consolidation (After External Edits)

```bash
# Repair links and media after database modifications
python mywi.py land consolidate --name="MyResearch" --depth=0
```

### 6. Embeddings & Pseudolinks

```bash
# Generate paragraph embeddings
python mywi.py embedding generate --name="MyResearch" --limit=1000

# Compute similarity (choose method)
# Option A: Exact cosine (small datasets)
python mywi.py embedding similarity --name="MyResearch" \
  --method=cosine --threshold=0.85 --minrel=1

# Option B: Approximate LSH (large datasets)
python mywi.py embedding similarity --name="MyResearch" \
  --method=cosine_lsh --lshbits=20 --topk=15 --threshold=0.85 --maxpairs=5000000

# Option C: ANN + NLI (semantic relations)
python mywi.py embedding similarity --name="MyResearch" \
  --method=nli --backend=faiss --topk=50 --maxpairs=2000000

# Export pseudolinks
python mywi.py land export --name="MyResearch" --type=pseudolinks
```

### 7. Export & Analysis

```bash
# CSV exports
python mywi.py land export --name="MyResearch" --type=pagecsv
python mywi.py land export --name="MyResearch" --type=fullpagecsv --minrel=1

# Graph exports (GEXF for Gephi)
python mywi.py land export --name="MyResearch" --type=pagegexf
python mywi.py land export --name="MyResearch" --type=nodegexf

# Text corpus
python mywi.py land export --name="MyResearch" --type=corpus

# Media
python mywi.py land export --name="MyResearch" --type=mediacsv

# Pseudolinks aggregations
python mywi.py land export --name="MyResearch" --type=pseudolinkspage
python mywi.py land export --name="MyResearch" --type=pseudolinksdomain

# Tags
python mywi.py tag export --name="MyResearch" --type=matrix
```

---

## Configuration Guide

### Installation Wizards

```bash
# Basic setup (paths, network, user agent)
python scripts/install-basic.py

# API keys (SerpAPI, SEO Rank, OpenRouter)
python scripts/install-api.py

# LLM/embeddings configuration
python scripts/install-llm.py

# Docker Compose setup
python scripts/install-docker-compose.py --level [basic|api|llm]
```

### Key Settings (settings.py)

#### Storage & Network

```python
data_location = "/path/to/data"  # Database and files
user_agent = "Mozilla/5.0..."    # HTTP user agent
parallel_connections = 5         # Concurrent connections
default_timeout = 30             # Request timeout (seconds)
```

#### Media Analysis

```python
dynamic_media_extraction = False  # Playwright headless browser
media_min_width = 200            # Minimum image width
media_max_file_size = 10485760   # Max file size (bytes)
media_max_colors = 5             # Dominant colors to extract
```

#### Embeddings

```python
embed_provider = 'http'          # 'fake', 'http', 'openai', 'mistral', 'gemini', 'huggingface', 'ollama'
embed_model_name = 'text-embedding-3-small'
embed_batch_size = 100
embed_min_paragraph_chars = 50
embed_max_paragraph_chars = 2000
embed_similarity_method = 'cosine'  # 'cosine', 'cosine_lsh'
embed_similarity_threshold = 0.85
```

#### NLI (Natural Language Inference)

```python
nli_model_name = 'MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7'
nli_fallback_model_name = 'typeform/distilbert-base-uncased-mnli'
nli_backend_preference = 'auto'  # 'auto', 'transformers', 'crossencoder', 'fallback'
nli_batch_size = 64
nli_max_tokens = 512
nli_torch_num_threads = 4
similarity_backend = 'faiss'     # 'faiss', 'bruteforce'
similarity_top_k = 50
```

#### API Keys

```python
serpapi_api_key = 'your_key_here'  # Or MWI_SERPAPI_API_KEY env var
seorank_api_key = 'your_key_here'  # Or MWI_SEORANK_API_KEY env var
openrouter_enabled = False
openrouter_api_key = 'your_key_here'  # Or MWI_OPENROUTER_API_KEY
openrouter_model = 'openai/gpt-4o-mini'
```

#### Heuristics (Domain-Specific)

```python
heuristics = {
    "www.youtube.com": {
        "regex": r'watch\?v=([a-zA-Z0-9_-]+)',
        "template": "https://www.youtube.com/watch?v={}"
    },
    # ... more domain patterns
}
```

---

## Development Guidelines

### Code Style

- **Python 3.10+** features encouraged
- **Docstrings**: Google-style format
- **Type hints**: Preferred but not mandatory
- **Line length**: ~100 characters
- **Imports**: Standard library → Third-party → Local

### Key Algorithms

#### Relevance Scoring

```python
# Weighted sum of lemma hits
relevance = (title_hits * 3) + (description_hits * 2) + content_hits
```

- Title matches weighted 3x
- Description matches weighted 2x
- Content matches weighted 1x

#### Mercury Parser Merge Strategies

| Strategy | Behavior |
|----------|----------|
| `smart_merge` | Intelligent field-by-field (default) |
| `mercury_priority` | Mercury always wins |
| `preserve_existing` | Only fill empty fields |

#### Media Analysis Pipeline

1. Extract media URLs from HTML
2. Optional: Playwright dynamic extraction
3. Download media files
4. Extract metadata (dimensions, format, EXIF)
5. Compute dominant colors (K-means clustering)
6. Generate perceptual hash (imagehash)
7. Store in database

#### Async Crawling Pattern

```python
async def crawl_batch(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### Adding New Export Types

1. Add function to `mwi/export.py`: `def write_<type>(land, filepath, **kwargs)`
2. Register in `Export` class method mapping
3. Update controller in `mwi/controller.py`
4. Add to documentation

### Language Support

- Default: French (`fr`)
- NLTK tokenization + French stemming
- Language codes in Land: comma-separated (e.g., `"fr,en,de"`)
- Override with `--lang` parameter

---

## Testing Strategy

### Test Coverage

```bash
# All tests
pytest tests/

# With coverage
pytest --cov=mwi tests/

# Specific module
pytest tests/test_cli.py -v

# Single test
pytest tests/test_cli.py::test_functional_test -v
```

### Test Files

- `test_cli.py`: CLI argument parsing and execution
- `test_core.py`: Core algorithms (crawl, parse, score)
- `test_metadata*.py`: Metadata extraction
- `test_expression_metadata.py`: Expression handling

### CI/CD Notes

- Tests use temporary databases
- Mock external APIs (SerpAPI, SEO Rank, OpenRouter)
- Async tests use `pytest-asyncio`

---

## Export Capabilities

### Land Exports

| Type | Format | Description | Use Case |
|------|--------|-------------|----------|
| `pagecsv` | CSV | Pages with metadata | Spreadsheet analysis |
| `fullpagecsv` | CSV | Pages + full content | Text mining |
| `pagegexf` | GEXF | Page link graph | Gephi visualization |
| `nodecsv` | CSV | Domain nodes | Network analysis |
| `nodegexf` | GEXF | Domain graph | Network visualization |
| `mediacsv` | CSV | Media links | Media inventory |
| `corpus` | TXT | Raw text corpus | NLP processing |
| `pseudolinks` | CSV | Paragraph pairs | Semantic analysis |
| `pseudolinkspage` | CSV | Page-level aggregation | Network metrics |
| `pseudolinksdomain` | CSV | Domain-level aggregation | Macro patterns |

### Tag Exports

| Type | Format | Description |
|------|--------|-------------|
| `matrix` | CSV | Tag co-occurrence matrix |
| `content` | CSV | Tagged content snippets |

### Export with Filters

```bash
# Minimum relevance filter
python mywi.py land export --name="MyResearch" --type=pagecsv --minrel=1.5

# Combines with all export types
python mywi.py land export --name="MyResearch" --type=corpus --minrel=2
```

---

## Advanced Features

### Module Responsibilities

#### core.py - Core Algorithms
- **Web Crawling**: Async batch crawling with aiohttp
- **Content Extraction**: Trafilatura + BeautifulSoup
- **Relevance Scoring**: Weighted lemma matching (title×3 + desc×2 + content×1)
- **Link Discovery**: Automatic link extraction and graph construction
- **Media Extraction**: Static + dynamic (Playwright) media detection
- **Domain Management**: Domain-level metadata extraction
- **NLTK Integration**: Tokenization with fallback for missing punkt data
- **Helper Functions**: URL resolution, confirmation prompts, argument checking

#### embedding_pipeline.py - Embeddings
- **Paragraph Splitting**: Smart text chunking with length filters
- **Provider Support**:
  - `fake`: Deterministic local embeddings (testing)
  - `http`: Generic HTTP endpoint
  - `openai`: OpenAI API
  - `mistral`: Mistral AI API
  - `gemini`: Google Gemini API
  - `huggingface`: HuggingFace Inference API
  - `ollama`: Local Ollama server
- **Batch Processing**: Configurable batch sizes per provider
- **Vector Storage**: JSON serialization in SQLite
- **Similarity Methods**:
  - `cosine`: Exact O(n²) pairwise
  - `cosine_lsh`: LSH approximate with hyperplanes

#### semantic_pipeline.py - NLI Relations
- **ANN Recall**: FAISS or brute-force k-NN search
- **Cross-Encoder NLI**: Entailment/neutral/contradiction classification
- **Relation Scoring**: RelationScore ∈ {-1, 0, 1} + ConfidenceScore
- **Backends**:
  - `faiss`: Fast approximate nearest neighbors (optional)
  - `bruteforce`: Fallback exact search
- **Models**:
  - Multilingual: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`
  - English: `typeform/distilbert-base-uncased-mnli`
- **Performance Tuning**: Thread control, batch sizes, progress tracking

#### llm_openrouter.py - LLM Validation
- **Relevance Check**: AI-powered yes/no filtering
- **Prompt Building**: French-language prompts with land context
- **Response Normalization**: "oui"/"non" extraction
- **Call Tracking**: Global call counter for rate limiting
- **Integration Points**:
  - During crawl/readable (optional)
  - Bulk validation command (`land llm validate`)

#### media_analyzer.py - Media Analysis
- **Download & Fetch**: Async image/video/audio fetching
- **Metadata Extraction**:
  - Dimensions (width, height)
  - File size and format
  - Color mode (RGB, RGBA, L)
  - Aspect ratio
  - EXIF data (GPS, camera, etc.)
- **Visual Analysis**:
  - Dominant colors (K-means clustering)
  - Web-safe colors
  - Transparency detection
  - Perceptual hashing (imagehash)
- **Filtering**: Configurable min/max dimensions and file sizes
- **Error Handling**: Graceful failure with error logging

#### readable_pipeline.py - Mercury Parser
- **External Tool**: Requires `@postlight/mercury-parser` npm package
- **Content Extraction**: High-quality article extraction
- **Merge Strategies**:
  - `smart_merge`: Field-type-based intelligent fusion
  - `mercury_priority`: Mercury always overwrites
  - `preserve_existing`: Only fill empty fields
- **Bidirectional Logic**: Handles empty DB, empty Mercury, or both full
- **Enrichment**: Automatic media/link extraction and relevance recalculation
- **Batch Processing**: Sequential with progress tracking

#### export.py - Data Export
- **CSV Exports**: Pages, nodes, media, pseudolinks (3 levels)
- **GEXF Exports**: Network graphs for Gephi with attributes
- **Corpus Export**: ZIP archives with Dublin Core metadata
- **Tag Exports**: Matrix (co-occurrence) and content formats
- **SEO Rank Integration**: Extracts JSON payloads into CSV columns
- **SQL Templating**: Dynamic column mapping for flexible queries
- **Unicode Handling**: Proper encoding for international characters

### Mercury Parser Pipeline

**Prerequisites:** `npm install -g @postlight/mercury-parser`

**Features:**
- High-quality content extraction
- Automatic media/link enrichment
- Configurable merge strategies
- Bidirectional logic (preserves existing data intelligently)

**Merge Strategies:**

```bash
# Smart merge (recommended)
python mywi.py land readable --name="MyTopic" --merge=smart_merge

# Mercury priority
python mywi.py land readable --name="MyTopic" --merge=mercury_priority

# Preserve existing
python mywi.py land readable --name="MyTopic" --merge=preserve_existing
```

### OpenRouter LLM Validation

**Purpose:** AI-powered relevance filtering

**Setup:**
```python
# settings.py
openrouter_enabled = True
openrouter_api_key = 'sk-...'
openrouter_model = 'openai/gpt-4o-mini'
openrouter_timeout = 15
openrouter_readable_max_chars = 6000
openrouter_max_calls_per_run = 500
```

**Usage:**
```bash
# During readable extraction
python mywi.py land readable --name="MyTopic" --llm=true

# Bulk validation
python mywi.py land llm validate --name="MyTopic" --limit=100
```

### SEO Rank Enrichment

**API Fields:**
- `sr_rank`: Global SEO rank
- `sr_kwords`: Tracked keywords
- `sr_traffic`: Estimated monthly visits
- `sr_costs`: Ad-equivalent cost (USD)
- `sr_ulinks`: Outgoing links
- `sr_hlinks`: Total backlinks
- `sr_dlinks`: Referring domains
- `fb_comments`, `fb_shares`, `fb_reac`: Facebook metrics

**Stored as:** Raw JSON in `expression.seorank`

### Embeddings Architecture

**Providers:**
- `fake`: Deterministic local (testing)
- `http`: Generic HTTP endpoint
- `openai`: OpenAI API
- `mistral`: Mistral AI API
- `gemini`: Google Gemini API
- `huggingface`: HuggingFace Inference API
- `ollama`: Local Ollama

**Similarity Methods:**
- `cosine`: Exact O(n²) pairwise
- `cosine_lsh`: LSH approximate
- `nli`: ANN + Cross-Encoder semantic

**Environment Variables:**
```bash
export OMP_NUM_THREADS=8              # OpenMP threads
export MKL_NUM_THREADS=8              # MKL threads
export OPENBLAS_NUM_THREADS=8         # OpenBLAS threads
export TOKENIZERS_PARALLELISM=false   # Disable tokenizer warnings
```

### Dynamic Media Extraction

**Requires:** Playwright (`python install_playwright.py`)

**Enable:**
```python
# settings.py
dynamic_media_extraction = True
```

**Features:**
- JavaScript-rendered media
- Lazy-loaded images
- AJAX-loaded content
- Social media embeds

---

## Troubleshooting

### Database Issues

```bash
# Schema out of date
python mywi.py db migrate

# Corrupted database
scripts/sqlite_recover.sh data/mwi.db data/mwi_repaired.db

# Test repaired DB
MYWI_DATA_DIR="$PWD/data/test-repaired" python mywi.py land list

# Backup before operations
cp data/mwi.db data/mwi.db.bak_$(date +%Y%m%d_%H%M%S)
```

### NLTK Download Issues (Windows/macOS)

```bash
python -m nltk.downloader punkt punkt_tab

# SSL errors
pip install --upgrade certifi
```

### Embeddings/NLI Issues

```bash
# Check environment
python mywi.py embedding check

# All score_raw=0.5 → neutral fallback
# Solution: Install ML dependencies
pip install -r requirements-ml.txt

# Missing score_raw column
python mywi.py db migrate

# macOS OpenMP segfaults
export OMP_NUM_THREADS=1
export KMP_DUPLICATE_LIB_OK=TRUE
```

### Performance Tuning

**Large lands (100k+ paragraphs):**
```bash
# Use LSH method
python mywi.py embedding similarity --name="Large" \
  --method=cosine_lsh --lshbits=20 --topk=15 \
  --threshold=0.88 --maxpairs=8000000
```

**NLI slow scoring:**
- Lower `nli_batch_size` (default: 64)
- Raise `--minrel` to filter paragraphs
- Cap with `--maxpairs`
- Increase threads moderately (`OMP_NUM_THREADS`)

**Too many pairs:**
- Raise `--threshold`
- Increase `--lshbits`
- Lower `--topk`
- Use `--minrel` filter

### Docker Issues

```bash
# Container not starting
docker compose logs mwi

# Rebuild image
docker compose build --no-cache

# Access container
docker compose exec mwi bash

# Volume permissions
ls -la ./data
```

---

## Security & Permissions

### Allowed Commands (Claude Code)

From `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python test:*)",
      "Bash(python3:*)",
      "Bash(python:*)"
    ],
    "deny": []
  }
}
```

### API Keys Security

**Never commit:**
- `settings.py` with real keys
- `.env` files

**Best practices:**
- Use environment variables
- Add to `.gitignore`
- Rotate keys regularly

**Environment variables:**
```bash
export MWI_SERPAPI_API_KEY='...'
export MWI_SEORANK_API_KEY='...'
export MWI_OPENROUTER_API_KEY='...'
export MYWI_DATA_DIR='/custom/path'
```

### Data Privacy

- SQLite database: `data/mwi.db`
- Crawled content: Plain text in DB
- Media files: Downloaded to `data/`
- Embeddings: Stored as JSON arrays

**Sensitive data:**
- Review before committing
- Use `.gitignore` for data directories
- Sanitize exports before sharing

---

## Docker Reference

### Docker Compose (Recommended)

```bash
# One-command setup
./scripts/docker-compose-setup.sh [basic|api|llm]

# Manual setup
python scripts/install-docker-compose.py --level llm
docker compose up -d --build
docker compose exec mwi python mywi.py db setup

# Management
docker compose up -d       # Start
docker compose down        # Stop
docker compose logs mwi    # Logs
docker compose exec mwi bash  # Shell
```

### Manual Docker

```bash
# Build
docker build -t mwi:latest .

# Run with volume
docker run -dit --name mwi -v ~/mywi_data:/app/data mwi:latest

# Execute commands
docker exec -it mwi python mywi.py land list

# Management
docker stop mwi
docker start mwi
docker rm mwi
```

### Data Persistence

- **Host:** `./data` (or path in `.env`)
- **Container:** `/app/data`
- **Mapping:** Automatic via docker-compose.yml

---

## Complete CLI Arguments Reference

### Global Arguments (Available for Most Commands)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--name` | str | - | Name of the object (land, domain, etc.) |
| `--desc` | str | - | Description of the object |
| `--lang` | str | `fr` | Language code(s), comma-separated (e.g., "fr,en") |
| `--limit` | int | - | Maximum number of items to process |
| `--minrel` | int/float | - | Minimum relevance threshold filter |
| `--maxrel` | int/float | - | Maximum relevance threshold filter |
| `--depth` | int | - | Crawl depth filter (0 = seeds, 1 = depth 1, etc.) |
| `--http` | str | - | HTTP status filter (e.g., "200", "503", "all") |

### Land-Specific Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--land` | str | - | Name of the land to work with (synonym for --name in land context) |
| `--terms` | str | - | Comma-separated keywords to add to land dictionary |
| `--urls` | str | - | Comma-separated URLs to add to land |
| `--path` | str | - | Path to file containing URLs (one per line) |
| `--type` | str | - | Export type (pagecsv, pagegexf, corpus, etc.) |
| `--merge` | str | `smart_merge` | Readable merge strategy (smart_merge, mercury_priority, preserve_existing) |
| `--llm` | str | `false` | Enable OpenRouter validation during readable (true/false) |
| `--force` | flag | false | Force refresh/reprocess existing data |

### SerpAPI (urlist) Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--query` | str | - | Search query for SerpAPI (Boolean operators supported) |
| `--engine` | str | `google` | Search engine (google, bing, duckduckgo) |
| `--datestart` | str | - | Start date for filtering (YYYY-MM-DD) |
| `--dateend` | str | - | End date for filtering (YYYY-MM-DD) |
| `--timestep` | str | `week` | Date window size (day, week, month) |
| `--sleep` | float | 1.0 | Delay between API calls (seconds) |
| `--progress` | flag | false | Display progress per date window |

### Embedding & Similarity Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--threshold` | float | - | Similarity threshold (typically 0.80-0.95) |
| `--method` | str | `cosine` | Similarity method (cosine, cosine_lsh, nli) |
| `--backend` | str | - | ANN backend (bruteforce, faiss) |
| `--topk` | int | - | Top-K nearest neighbors per paragraph |
| `--lshbits` | int | - | Number of LSH hyperplanes (for cosine_lsh) |
| `--maxpairs` | int | - | Maximum number of similarity pairs to store |

### Command Patterns

```bash
# Basic pattern
python mywi.py <object> <verb> [options]

# Nested command pattern
python mywi.py <object> <verb> <subverb> [options]

# Examples
python mywi.py db setup
python mywi.py land create --name="Topic"
python mywi.py land llm validate --name="Topic" --force
python mywi.py embedding similarity --name="Topic" --method=nli
```

---

## Common Patterns for AI Assistants

### When Asked to "Crawl a Website"

```bash
# Full workflow
python mywi.py land create --name="NewTopic" --desc="Description"
python mywi.py land addurl --land="NewTopic" --urls="https://example.com"
python mywi.py land crawl --name="NewTopic" --limit=100
python mywi.py land readable --name="NewTopic"
python mywi.py land export --name="NewTopic" --type=pagecsv
```

### When Asked to "Analyze Content"

```bash
# Add keywords
python mywi.py land addterm --land="Topic" --terms="keyword1, keyword2"

# Recrawl to update relevance
python mywi.py land crawl --name="Topic" --limit=50

# Export high-relevance only
python mywi.py land export --name="Topic" --type=fullpagecsv --minrel=1
```

### When Asked to "Find Similar Content"

```bash
# Generate embeddings
python mywi.py embedding generate --name="Topic"

# Compute similarity
python mywi.py embedding similarity --name="Topic" --method=cosine --threshold=0.85

# Export pseudolinks
python mywi.py land export --name="Topic" --type=pseudolinks
```

### When Asked to "Fix Database Issues"

```bash
# Update schema
python mywi.py db migrate

# Repair links/media after external edits
python mywi.py land consolidate --name="Topic"

# Recover corrupted DB
scripts/sqlite_recover.sh data/mwi.db data/mwi_repaired.db
```

### When Asked About Performance

**Small datasets (< 10k pages):**
- Use default settings
- Exact cosine similarity
- No need for LSH or FAISS

**Medium datasets (10k-100k pages):**
- Use `cosine_lsh` method
- `--lshbits=20`, `--topk=15`
- Filter with `--minrel=1`

**Large datasets (100k+ pages):**
- Use `cosine_lsh` with strict filters
- `--threshold=0.88`, `--maxpairs=5000000`
- Batch crawling: `for i in {1..100}; do python mywi.py land crawl --name="Topic" --limit=100; done`

---

## Project History & Context

### Git Status

**Current branch:** master
**Main branch:** master
**Status:** Clean (no uncommitted changes)

**Recent commits:**
```
a4dfdcb DOCSTRING Documention functions
5b0b105 README fr Update bis
78a0326 unstall ssh debug
f1f62cf Ignore AGENTS.md in repository history
b8227d8 README fr Update
```

### Development Focus

- Comprehensive docstrings (recent effort)
- Documentation improvements (French + English)
- Stability and error handling
- Performance optimization for large datasets

### Known Exclusions

- `AGENTS.md` ignored in git history (this file!)
- Local settings files (`settings.py`, `.env`)
- Data directories (`data/`)
- Virtual environments (`.venv/`, `venv/`)

---

## Quick Reference Card

### Essential Commands

```bash
# Setup
python mywi.py db setup                    # Initialize
python mywi.py db migrate                  # Update schema

# Land operations
python mywi.py land create --name=X --desc=Y
python mywi.py land list [--name=X]
python mywi.py land addterm --land=X --terms="a, b, c"
python mywi.py land addurl --land=X --urls="https://..."
python mywi.py land crawl --name=X [--limit=N]
python mywi.py land readable --name=X
python mywi.py land export --name=X --type=pagecsv

# Embeddings
python mywi.py embedding generate --name=X
python mywi.py embedding similarity --name=X --method=cosine
python mywi.py embedding check

# Testing
pytest tests/
pytest tests/test_cli.py -v
```

### Files to Check First

1. **README.md** - User documentation
2. **.claude/CLAUDE.md** - AI assistant instructions
3. **mwi/model.py** - Database schema
4. **mwi/core.py** - Core algorithms
5. **settings.py** - Configuration (if exists)

### Getting Help

- **CLI help:** Commands have built-in help (check `mwi/cli.py`)
- **Tests:** Show usage patterns (`tests/test_*.py`)
- **Scripts:** Interactive wizards (`scripts/install-*.py`)
- **Logs:** Check console output for detailed errors

---

## Conclusion

This document provides comprehensive context for AI coding assistants working on MyWebIntelligence. It covers:

✅ Architecture and design patterns
✅ Complete command reference
✅ Configuration options
✅ Development workflows
✅ Troubleshooting guides
✅ Best practices and conventions

**For AI Assistants:**
- Use this as primary reference for project understanding
- Refer to code files for implementation details
- Check tests for usage examples
- Consult README.md for user-facing documentation

**Last Updated:** 2025-10-02
**Project Version:** Based on commit a4dfdcb
**Maintained by:** Project contributors + AI-assisted documentation

---

## AI Assistant Quick Reference

### Files to Read First When Working On...

**Database/Schema Issues:**
1. `mwi/model.py` - Complete schema definitions
2. `migrations/` - Migration scripts
3. `mwi/controller.py` → `DbController`

**Crawling/Content Extraction:**
1. `mwi/core.py` - Main crawling logic
2. `mwi/readable_pipeline.py` - Mercury Parser integration
3. `settings.py` - Crawl configuration

**Data Export:**
1. `mwi/export.py` - All export formats
2. `mwi/controller.py` → `LandController.export()`
3. README.md - Export format documentation

**Embeddings/Similarity:**
1. `mwi/embedding_pipeline.py` - Vector generation
2. `mwi/semantic_pipeline.py` - NLI and ANN
3. `mwi/controller.py` → `EmbeddingController`

**Media Analysis:**
1. `mwi/media_analyzer.py` - Image/video processing
2. `mwi/core.py` → `extract_dynamic_medias()`
3. `settings.py` - Media configuration

**CLI/Commands:**
1. `mwi/cli.py` - Argument parsing
2. `mwi/controller.py` - Command dispatch
3. `mywi.py` - Entry point

### Common Code Patterns

**Adding a new CLI command:**
```python
# 1. Add argument to cli.py parser
parser.add_argument('--newarg', type=str, help='...')

# 2. Add controller method
class LandController:
    @staticmethod
    def newcommand(args: core.Namespace):
        core.check_args(args, 'name')
        land = model.Land.get_or_none(model.Land.name == args.name)
        # ... implementation

# 3. Register in dispatch()
'land': {
    'newcommand': LandController.newcommand,
}
```

**Adding a new export format:**
```python
# In export.py
def write_newformat(self, filename) -> int:
    """Export description."""
    cursor = self.get_sql_cursor(SQL_QUERY, COLUMN_MAP)
    # Use write_csv() or custom logic
    return self.write_csv(filename, KEYS, cursor)
```

**Querying with relevance filter:**
```python
query = (model.Expression
         .select()
         .where(
             (model.Expression.land == land) &
             (model.Expression.relevance >= minrel)
         ))
```

**Async batch processing:**
```python
async def process_batch(items):
    connector = aiohttp.TCPConnector(limit=settings.parallel_connections)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_item(session, item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### Important Constraints

1. **NLTK Fallback**: Always check `_NLTK_OK` flag; use `_simple_word_tokenize()` as fallback
2. **Windows Async**: Use `ProactorEventLoop` on Windows for async operations
3. **Optional Dependencies**: Check availability before using (Playwright, FAISS, sentence-transformers)
4. **Database Migrations**: Always use `db migrate` after schema changes, never direct SQL
5. **French Default**: All prompts and messages default to French unless specified
6. **URL Resolution**: Always use `resolve_url()` from core for relative URLs
7. **Peewee Cascades**: Foreign keys have `on_delete='CASCADE'` - deletions propagate
8. **JSON Fields**: Media colors, EXIF, embeddings stored as JSON strings - use `json.loads()`

### Testing Guidelines

**Test Structure:**
- CLI tests: `tests/test_cli.py`
- Core logic: `tests/test_core.py`
- Metadata: `tests/test_metadata*.py`

**Running Tests:**
```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_cli.py -v

# With coverage
pytest --cov=mwi tests/

# Single test
pytest tests/test_cli.py::test_name -v
```

**Mock External APIs:**
- SerpAPI calls
- SEO Rank API calls
- OpenRouter LLM calls
- Use temporary databases for isolation

### Performance Optimization Tips

**Small Lands (< 1k pages):**
- Default settings work fine
- No special optimization needed

**Medium Lands (1k-10k pages):**
- Use `--limit` for batch processing
- Consider `--minrel` to filter noise
- Sequential crawling is acceptable

**Large Lands (10k-100k pages):**
- Use `cosine_lsh` for similarity
- Batch crawls: loop with `--limit=100`
- Filter aggressively with `--minrel=2`
- Use `--maxpairs` to cap similarity results

**Very Large Lands (100k+ pages):**
- Mandatory LSH: `--lshbits=20`, `--topk=15`
- High threshold: `--threshold=0.88`
- Consider FAISS for NLI: `--backend=faiss`
- Parallelize with multiple processes if needed

### Debugging Checklist

**Database Issues:**
- [ ] Run `python mywi.py db migrate`
- [ ] Check `data/mwi.db` exists and is not locked
- [ ] Verify `settings.data_location` is correct
- [ ] Check disk space

**Crawling Issues:**
- [ ] Verify `settings.user_agent` is set
- [ ] Check network connectivity
- [ ] Review `settings.parallel_connections` (reduce if throttled)
- [ ] Check `settings.default_timeout` (increase for slow sites)

**Embedding Issues:**
- [ ] Run `python mywi.py embedding check`
- [ ] Verify API keys for chosen provider
- [ ] Check `embed_provider` in settings
- [ ] Ensure `embed_api_url` is correct for HTTP provider

**NLI Issues:**
- [ ] Install: `pip install -r requirements-ml.txt`
- [ ] Check available RAM (NLI models are large)
- [ ] Verify `OMP_NUM_THREADS` environment variable
- [ ] Consider fallback model if main model fails

**Export Issues:**
- [ ] Verify land exists: `python mywi.py land list`
- [ ] Check disk space for exports
- [ ] Verify `--type` is valid
- [ ] Use `--minrel` if too many results

---

## Summary for AI Assistants

MyWebIntelligence is a **mature, production-ready** web intelligence tool with:

✅ **Comprehensive CLI** - 50+ commands across 6 controllers
✅ **Robust Architecture** - MVC-like pattern with async I/O
✅ **Rich Data Model** - 13+ tables with proper relations
✅ **Advanced Features** - Embeddings, NLI, LLM validation, media analysis
✅ **Multiple Export Formats** - CSV, GEXF, ZIP corpus, 3-level pseudolinks
✅ **Production Deployments** - Docker support, migration system
✅ **Extensive Documentation** - README (FR/EN), inline docstrings, this file

**When assisting users:**
1. Start with land creation workflow (create → addterm → addurl → crawl → readable → export)
2. Suggest appropriate filters (`--minrel`, `--depth`, `--limit`) for performance
3. Recommend LSH for large datasets, exact cosine for small
4. Always mention optional dependencies (Playwright, Mercury Parser, FAISS)
5. Reference specific files and line numbers when explaining implementations
6. Use examples from README.md and tests/ for proven patterns

**Last Updated:** 2025-10-02
**Project Version:** Based on commit a4dfdcb
