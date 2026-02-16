# MyWebIntelligence API

API FastAPI encapsulant les fonctionnalités du crawler MyWebIntelligencePython pour permettre son intégration avec MyWebClient et ouvrir la voie à un déploiement SaaS scalable.

## 🚀 Démarrage Rapide

### Prérequis

- Docker et Docker Compose
- Python 3.11+ (pour le développement local)
- PostgreSQL 15+ (ou utiliser Docker)
- Redis (ou utiliser Docker)

### Installation avec Docker

1. Cloner le projet
```bash
git clone <repository-url>
cd MyWebIntelligenceAPI
```

2. Copier le fichier de configuration
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
```

3. Lancer les services
```bash
docker-compose up -d
```

4. Créer la base de données
```bash
docker-compose exec api alembic upgrade head
```

5. L'API est maintenant accessible sur http://localhost:8000
   - Documentation interactive : http://localhost:8000/docs
   - Alternative ReDoc : http://localhost:8000/redoc

### Installation pour le développement

1. Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

2. Installer les dépendances
```bash
pip install -r requirements.txt
```

3. Configurer les variables d'environnement
```bash
cp .env.example .env
# Éditer .env
```

4. Lancer PostgreSQL et Redis (via Docker ou localement)
```bash
docker-compose up -d postgres redis
```

5. Créer la base de données
```bash
alembic upgrade head
```

6. Lancer l'API
```bash
uvicorn app.main:app --reload --port 8000
```

7. Lancer Celery Worker (dans un autre terminal)
```bash
celery -A app.core.celery_app worker --loglevel=info
```

## 📚 Documentation API

### Authentification

L'API utilise JWT pour l'authentification. Pour obtenir un token :

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@example.com&password=yourpassword"
```

Utiliser le token dans les requêtes suivantes :
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/lands
```

### Endpoints de Crawling

- `POST /lands/{land_id}/crawl`: Lance une tâche de crawling pour un land.
- `POST /lands/{land_id}/consolidate`: Lance une tâche de consolidation pour un land.

### Endpoints d'Exportation

- `POST /export/`: Crée une nouvelle tâche d'exportation pour un land.


#### Lands (Projets de crawling)
- `GET /api/v1/lands` - Liste des lands
- `POST /api/v1/lands` - Créer un land
- `GET /api/v1/lands/{id}` - Détails d'un land
- `PUT /api/v1/lands/{id}` - Modifier un land
- `DELETE /api/v1/lands/{id}` - Supprimer un land
- `POST /api/v1/lands/{id}/crawl` - Lancer le crawling

#### Expressions (Pages crawlées)
- `GET /api/v1/expressions` - Liste des expressions
- `GET /api/v1/expressions/{id}` - Détails d'une expression
- `PUT /api/v1/expressions/{id}` - Modifier une expression
- `DELETE /api/v1/expressions/{id}` - Supprimer une expression

#### Jobs (Tâches asynchrones)
- `GET /api/v1/jobs/{id}` - Statut d'un job
- `POST /api/v1/jobs/{id}/cancel` - Annuler un job

### WebSocket pour le suivi en temps réel

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/jobs/JOB_ID');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Progress:', data.progress);
};
```

## 🔧 Configuration

### Variables d'environnement principales

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | URL de connexion PostgreSQL | postgresql://... |
| `REDIS_URL` | URL de connexion Redis | redis://redis:6379 |
| `SECRET_KEY` | Clé secrète pour JWT | (générer une clé) |
| `FIRST_SUPERUSER_EMAIL` | Email du premier admin | admin@example.com |
| `FIRST_SUPERUSER_PASSWORD` | Mot de passe admin | changethispassword |

Voir `.env.example` pour la liste complète.

## 🏗️ Architecture

```
MyWebIntelligenceAPI/
├── app/
│   ├── api/            # Endpoints REST
│   ├── core/           # Configuration, sécurité
│   ├── crud/           # Opérations CRUD
│   ├── db/             # Modèles SQLAlchemy
│   ├── schemas/        # Modèles Pydantic
│   ├── services/       # Logique métier
│   └── tasks/          # Tâches Celery
├── alembic/            # Migrations DB
├── tests/              # Tests unitaires
└── docker-compose.yml  # Configuration Docker
```

## 🧪 Tests

Lancer les tests :
```bash
pytest
```

Avec coverage :
```bash
pytest --cov=app tests/
```

## 🧭 Scénario d'usage complet

Un script `scripts/land_scenario.py` reproduit l'ancien workflow CLI : création d'un land, ajout de termes/URLs puis lancement d'un crawl.

```bash
python scripts/land_scenario.py \
  --land-name "MyResearchTopic" \
  --terms "keyword1,keyword2" \
  --urls "https://example.org,https://example.com" \
  --crawl-limit 25
```

Variables d'environnement prises en charge :

- `MYWI_BASE_URL` (par défaut `http://localhost:8000`)
- `MYWI_USERNAME` / `MYWI_PASSWORD` (par défaut `admin@example.com` / `changeme`)

## 🔍 Monitoring

### Flower (Monitoring Celery)
Accessible sur http://localhost:5555

### Prometheus
Métriques disponibles sur http://localhost:9090

### Grafana
Dashboards sur http://localhost:3001 (admin/admin)

## 🚢 Déploiement Production

1. Utiliser `Dockerfile.prod` et `docker-compose.prod.yml`
2. Configurer les variables d'environnement de production
3. Utiliser un reverse proxy (Nginx) devant l'API
4. Activer HTTPS
5. Configurer les sauvegardes PostgreSQL

## 📊 Migration depuis SQLite

Pour migrer une base SQLite existante vers PostgreSQL :

```bash
# Script de migration à venir
python scripts/migrate_sqlite_to_postgres.py --source /path/to/mwi.db
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

## 📝 Licence

[Insérer la licence ici]

## 🆘 Support

Pour toute question ou problème :
- Ouvrir une issue sur GitHub
- Documentation complète : [lien vers la doc]
- Contact : [email de support]
