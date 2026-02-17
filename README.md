Component repository (backend at scale, optional).
Start here for the main tool and installation: [https://github.com/MyWebIntelligence/mwi](https://github.com/MyWebIntelligence/mwi?utm_source=chatgpt.com)

# MyWebIntelligence

Plateforme de crawling web et d'analyse de contenu.

<!-- badges: start -->
![MyWebIntelligence Banner](https://raw.githubusercontent.com/MyWebIntelligence/mwiR/refs/heads/main/man/figures/mwibanner.png)
<!-- badges: end -->

## Architecture

```
┌──────────────────────────┐       ┌──────────────────────────┐
│   Client React 18        │       │   FastAPI Backend         │
│   (Vite + Bootstrap 5)   │──────▶│   (Uvicorn)              │
│   Port 3000              │  /api │   Port 8000               │
└──────────────────────────┘       └──────────┬───────────────┘
                                              │
                                   ┌──────────┼───────────────┐
                                   │          │               │
                                   ▼          ▼               ▼
                              PostgreSQL    Redis       Celery Worker
                              (donnees)    (cache +     (crawl, export,
                                           broker)      analyse)
```

Le client React se connecte a l'API FastAPI V2. Les taches longues (crawl, export, analyse LLM) sont executees en arriere-plan par Celery.

## Prerequis

- **Docker + Docker Compose** (methode recommandee)
- OU : Node.js 20+, Python 3.11+, PostgreSQL 15, Redis 7

## Installation rapide (Docker)

```bash
# 1. Cloner le depot
git clone <repository-url>
cd MyWebIntelligenceProject

# 2. Configurer l'environnement API
cp MyWebIntelligenceAPI/.env.example MyWebIntelligenceAPI/.env
# Editer .env : definir SECRET_KEY, FIRST_SUPERUSER_EMAIL/PASSWORD, etc.

# 3. Demarrer tous les services
docker compose up -d --build

# 4. Verifier
curl http://localhost:8000/docs    # Swagger API
open http://localhost:3000         # Client web
```

Les migrations de base de donnees sont appliquees automatiquement au demarrage.

### Services Docker

| Service | Container | Role | Port |
|---------|-----------|------|------|
| `db` | mwi-db | PostgreSQL 15 | interne |
| `redis` | mwi-redis | Cache + broker Celery | interne |
| `api` | mywebintelligenceapi | API FastAPI | 8000 |
| `celery_worker` | mwi-celery-worker | Taches de fond | - |
| `client` | mwi-client | Client React (Nginx) | 3000 |

### Commandes Docker utiles

```bash
docker compose logs -f api            # Logs API
docker compose logs -f celery_worker  # Logs Celery
docker compose restart api            # Redemarrer l'API
docker compose down                   # Arreter tout
docker compose down -v                # Arreter + supprimer les donnees
```

## Installation developpement (sans Docker)

### Backend (FastAPI)

```bash
cd MyWebIntelligenceAPI

# Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Dependances
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Editer .env : adapter DATABASE_URL pour PostgreSQL local
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mwi_db

# Demarrer l'API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Dans un autre terminal : demarrer Celery
celery -A app.core.celery_app worker --loglevel=info
```

### Frontend (React)

```bash
cd MyWebClient/client

# Installer les dependances
yarn install

# Demarrer le serveur de dev (port 3000, proxy API vers localhost:8000)
yarn dev
```

Le serveur Vite redirige automatiquement les appels `/api/*` vers `http://localhost:8000`.

### Build de production

```bash
cd MyWebClient/client
yarn build     # Genere le dossier dist/
yarn preview   # Previsualiser le build
```

## Configuration

Les variables d'environnement sont dans `MyWebIntelligenceAPI/.env`. Les plus importantes :

| Variable | Description | Defaut |
|----------|-------------|--------|
| `SECRET_KEY` | Cle de chiffrement JWT | **A definir** |
| `DATABASE_URL` | Connexion PostgreSQL | `postgresql+asyncpg://...` |
| `CELERY_BROKER_URL` | URL Redis pour Celery | `redis://redis:6379/1` |
| `FIRST_SUPERUSER_EMAIL` | Email admin initial | `admin@example.com` |
| `FIRST_SUPERUSER_PASSWORD` | Mot de passe admin | **A definir** |
| `OPENROUTER_API_KEY` | Cle API LLM (optionnel) | - |
| `CRAWL_MAX_DEPTH` | Profondeur max de crawl | `3` |
| `CRAWL_TIMEOUT` | Timeout par page (sec) | `30` |

Voir `.env.example` pour la liste complete.

## Fonctionnalites

### Gestion des Lands
Creer et gerer des projets de veille (lands) avec URLs de depart et parametres de crawl.

### Exploration des expressions
Naviguer, filtrer, trier et paginer les contenus collectes. Detail avec contenu lisible, metadonnees, medias.

### Tags et annotations
Arbre de tags hierarchique (drag & drop), annotation de passages texte, gestion du contenu tague.

### Visualisation graphe
Graphe interactif des pages et domaines (Sigma.js + Graphology), detection de communautes, zoom et selection de noeuds.

### Export
Export en GEXF, JSON, CSV, corpus texte. Suivi des jobs d'export en temps reel.

### Operations
Lancement de crawl, consolidation, extraction de contenu lisible, analyse LLM, SEO.

### Recherche
Recherche cross-lands avec filtres.

### Administration
Tableau de bord admin, gestion des utilisateurs.

## Structure du projet

```
.
├── MyWebClient/
│   └── client/                 # Client React 18 + Vite + Bootstrap 5
│       ├── src/
│       │   ├── api/            # Couche API (axios → FastAPI V2)
│       │   ├── app/            # Context.jsx (etat global legacy)
│       │   ├── auth/           # Authentification (JWT, login, register)
│       │   ├── components/     # Composants partages + explorateurs legacy
│       │   ├── features/       # Modules fonctionnels
│       │   │   ├── admin/      # Administration
│       │   │   ├── dashboard/  # Tableau de bord
│       │   │   ├── domains/    # Gestion des domaines
│       │   │   ├── export/     # Export de donnees
│       │   │   ├── expressions/# Exploration des expressions
│       │   │   ├── graph/      # Visualisation graphe
│       │   │   ├── lands/      # Gestion des lands
│       │   │   ├── legacy/     # Wrapper explorateur legacy
│       │   │   ├── operations/ # Operations de crawl et analyse
│       │   │   ├── search/     # Recherche cross-lands
│       │   │   └── tags/       # Tags et annotations
│       │   ├── hooks/          # Hooks React personnalises
│       │   └── layouts/        # MainLayout, AuthLayout
│       ├── vite.config.js      # Configuration Vite + proxy API
│       ├── Dockerfile          # Build multi-stage (Node + Nginx)
│       └── package.json
│
├── MyWebIntelligenceAPI/       # Backend FastAPI
│   ├── app/
│   │   ├── api/v1/            # Endpoints API v1
│   │   ├── api/v2/            # Endpoints API v2 (sync)
│   │   ├── core/              # Crawler, Celery, securite
│   │   ├── services/          # Logique metier
│   │   ├── db/                # Modeles SQLAlchemy, schemas Pydantic
│   │   ├── crud/              # Operations CRUD
│   │   └── tasks/             # Taches Celery
│   ├── tests/                 # Tests (unit, integration)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml          # Orchestration de tous les services
└── README.md                   # Ce fichier
```

## API

- **Documentation Swagger** : http://localhost:8000/docs
- **Documentation ReDoc** : http://localhost:8000/redoc
- **API v1** : `/api/v1/` (endpoints complets)
- **API v2** : `/api/v2/` (endpoints simplifies, sync)

### Authentification

L'API utilise JWT. Le client gere automatiquement le refresh des tokens.

```bash
# Obtenir un token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "changethispassword"}'

# Utiliser le token
curl http://localhost:8000/api/v1/lands/ \
  -H "Authorization: Bearer <access_token>"
```

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Frontend | React 18, Vite 5, Bootstrap 5, React Router 6 |
| UI composants | react-bootstrap, @dnd-kit, Sigma.js, Graphology |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic |
| Base de donnees | PostgreSQL 15 |
| Cache / Broker | Redis 7 |
| Taches async | Celery |
| Conteneurisation | Docker, Docker Compose |

## Roadmap

- [ ] End-to-end API alignee avec le pipeline mwi
- [ ] Endpoints versiones + politique de compatibilite
- [ ] Demo one-command + dataset d'exemple
- [ ] Tests CI (smoke tests + lint)

## Licence

MIT
