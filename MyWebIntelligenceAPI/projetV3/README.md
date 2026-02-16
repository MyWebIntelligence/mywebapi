# MyWebIntelligence V3 - Architecture Async/Parallèle

**Statut:** 🚧 EN DÉVELOPPEMENT
**Date de création:** 19 octobre 2025
**Raison:** Simplification de la V2 en version synchrone stable

---

## 🎯 Objectif

La **V3** représente l'évolution avancée de MyWebIntelligence avec des capacités async/parallèles pour améliorer les performances et la scalabilité. Cette version est en développement et nécessite résolution de bugs critiques avant production.

### Fonctionnalités V3

- ✅ **Crawling HTTP parallèle** : `asyncio.gather()` pour crawler plusieurs URLs simultanément
- ✅ **Pipeline readable asynchrone** : Extraction de contenu en parallèle avec fallbacks (Trafilatura → Archive.org)
- ✅ **Analyse média parallèle** : Traitement d'images concurrent avec PIL/sklearn
- ✅ **Système d'embeddings** : Génération de vecteurs pour recherche sémantique (OpenAI, Mistral)
- ✅ **WebSocket temps réel** : Monitoring de progression des jobs via WebSocket
- ⚠️ **Bugs connus** : Erreurs `greenlet_spawn` dans extraction de liens, conflicts SQLAlchemy session

---

## 🔄 Pourquoi V3 est séparée de V2?

La V2 reste **simple, stable et synchrone** pour garantir :
- Maintenance facile
- Debuggage rapide
- Pas de complexité async inutile pour la majorité des cas d'usage

La V3 ajoute **complexité et performance** pour :
- Crawls massifs (>1000 URLs)
- Analyse média intensive
- Recherche sémantique avancée
- Applications nécessitant temps réel

**Décision:** Garder V2 simple (prod stable) et développer V3 en parallèle (expérimental).

---

## 📦 Code déplacé de V2 vers V3

### Date de migration: 19 octobre 2025

### Core modules (async)
- `app/core/crawler_engine.py` → `projetV3/app/core/crawler_engine_async.py` (867 lignes)
  - AsyncCrawlerEngine avec parallélisation HTTP
  - Méthode `crawl_expressions_parallel()` avec `asyncio.gather()`
  - Support `max_concurrent` pour contrôle concurrence

- `app/core/media_processor.py` → `projetV3/app/core/media_processor_async.py` (286 lignes)
  - Analyse d'images asynchrone avec httpx
  - Extraction couleurs dominantes (sklearn)
  - Traitement EXIF et hashing

- `app/core/readable_*.py` → `projetV3/app/core/` (177 + 123 = 300 lignes)
  - Pipeline readable asynchrone
  - Fallbacks Trafilatura → Archive.org
  - Gestion markdown enrichi

- `app/core/websocket.py` → `projetV3/app/core/websocket.py` (36 lignes)
  - WebSocketManager pour progression temps réel
  - Broadcast aux clients connectés

- `app/core/embedding_providers/` → `projetV3/app/core/embedding_providers/` (tout le dossier)
  - Providers OpenAI, Mistral
  - Génération embeddings pour paragraphes
  - Calcul similarité cosinus

### Services async
- `app/services/readable_*.py` → `projetV3/app/services/` (3 fichiers)
- `app/services/embedding_service.py` → `projetV3/app/services/`

### Tasks Celery async complexes
- `app/tasks/readable_*.py` → `projetV3/app/tasks/` (3 fichiers)
- `app/tasks/embedding_tasks.py` → `projetV3/app/tasks/`
- `app/tasks/text_processing_tasks.py` → `projetV3/app/tasks/`
- `app/tasks/media_analysis_task.py` → `projetV3/app/tasks/`

### Documentation technique
- `.claude/tasks/async_parallele.md` → `projetV3/docs/`
- `.claude/tasks/README_TEST_ASYNC.md` → `projetV3/docs/`
- `.claude/tasks/QUICKSTART_TEST_ASYNC.md` → `projetV3/docs/`
- `.claude/tasks/align_sync_async.md` → `projetV3/docs/`

### Tests async
- `tests/test-crawl-async.sh` → `projetV3/tests/` (si existe)

---

## 🐛 Bugs connus à résoudre avant production

### 1. ❌ Erreur `greenlet_spawn` dans extraction de liens

**Symptôme:**
```
Error processing markdown link: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**Localisation:** `crawler_engine_async.py` lignes 546-624 (`_create_links_from_markdown`, `_extract_and_save_links`)

**Impact:**
- ✅ Crawl principal fonctionne
- ✅ Métadonnées extraites
- ❌ Liens entre expressions non créés
- ❌ Graphe de navigation incomplet

**Solution requise:** Refactoriser l'extraction de liens pour éviter appels synchrones dans contexte async

---

### 2. ❌ Conflicts SQLAlchemy session en mode parallèle

**Symptôme:**
```
sqlalchemy.exc.InterfaceError: another operation is in progress
```

**Impact:** Commits parallèles causent des conflicts de session

**Solution actuelle (partielle):**
- Phase 1: HTTP parallèle (`asyncio.gather`)
- Phase 2: DB séquentielle (1 commit par expression)

**Solution optimale requise:** Pool de sessions ou queue de commits

---

### 3. ⚠️ Performance dégradée sans tuning

**Problème:** `max_concurrent=10` par défaut peut être trop/pas assez selon infrastructure

**Solution requise:**
- Profiling pour déterminer optimal
- Configuration dynamique selon charge
- Rate limiting par domaine

---

## 📊 Comparaison V2 (Sync) vs V3 (Async/Parallèle)

| Aspect | V2 Sync | V3 Async |
|--------|---------|----------|
| **Durée (5 URLs)** | ~30s | ~10s (3x plus rapide) |
| **Concurrence HTTP** | 1 requête/fois | 10 requêtes simultanées |
| **Complexité code** | Simple | Modérée-Élevée |
| **Debugging** | Facile | Difficile (race conditions) |
| **Maintenance** | Faible | Moyenne-Élevée |
| **Stabilité** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ (bugs connus) |
| **Usage recommandé** | Production stable | Développement/Tests |

---

## 🚀 Roadmap V3

### Phase 1: Correction bugs critiques (2-3 jours)
- [ ] Résoudre `greenlet_spawn` dans extraction liens
- [ ] Implémenter pool de sessions SQLAlchemy
- [ ] Tests unitaires complets pour chaque composant async

### Phase 2: Performance tuning (1-2 jours)
- [ ] Profiling performance (HTTP vs DB vs Processing)
- [ ] Configuration dynamique `max_concurrent`
- [ ] Rate limiting par domaine
- [ ] Retry logic pour échecs HTTP

### Phase 3: Pipeline readable production-ready (2-3 jours)
- [ ] Stabiliser fallbacks Trafilatura → Archive.org
- [ ] Gestion erreurs robuste
- [ ] Tests de charge (100+ URLs)
- [ ] Monitoring métriques (Prometheus)

### Phase 4: Système embeddings complet (3-4 jours)
- [ ] Support providers additionnels (Cohere, Voyage)
- [ ] Génération paragraphes optimisée
- [ ] Index vectoriel (FAISS/Pinecone)
- [ ] API recherche sémantique

### Phase 5: WebSocket production (1 jour)
- [ ] Authentification WebSocket
- [ ] Reconnexion automatique
- [ ] Monitoring connexions actives

### Phase 6: Tests et déploiement (2-3 jours)
- [ ] Tests d'intégration complets
- [ ] Tests de performance (benchmark V2 vs V3)
- [ ] Documentation API complète
- [ ] Guide migration V2 → V3

**Estimation totale:** 12-18 jours de développement

---

## 🧪 Tests

### Tests unitaires
```bash
# Crawler async
pytest projetV3/tests/unit/test_crawler_async.py -v

# Media processor async
pytest projetV3/tests/unit/test_media_processor_async.py -v

# Embeddings
pytest projetV3/tests/unit/test_embeddings.py -v
```

### Tests d'intégration
```bash
# Crawl async complet
./projetV3/tests/test-crawl-async.sh

# Readable pipeline
./projetV3/tests/test-readable-async.sh
```

### Benchmarks
```bash
# Comparaison V2 vs V3
python projetV3/tests/benchmark_v2_vs_v3.py --urls 100
```

---

## 📚 Documentation technique

- [async_parallele.md](docs/async_parallele.md) - Plan de développement crawling parallèle
- [README_TEST_ASYNC.md](docs/README_TEST_ASYNC.md) - Procédure de test async
- [QUICKSTART_TEST_ASYNC.md](docs/QUICKSTART_TEST_ASYNC.md) - Guide rapide tests
- [align_sync_async.md](docs/align_sync_async.md) - Alignement sync/async (CRITIQUE)

---

## 💡 Notes de développement

### Bonnes pratiques async
1. **Toujours** utiliser `asyncio.create_task()` pour parallélisme
2. **Jamais** mélanger appels sync et async sans `run_in_executor()`
3. **Toujours** gérer timeouts avec `asyncio.wait_for()`
4. **Toujours** cleanup resources avec `try/finally` ou context managers

### Gestion SQLAlchemy async
```python
# ✅ BON - Session isolée par requête
async with AsyncSessionLocal() as session:
    result = await session.execute(query)
    await session.commit()

# ❌ MAUVAIS - Réutilisation session entre tasks parallèles
session = AsyncSessionLocal()
tasks = [process_url(session, url) for url in urls]
await asyncio.gather(*tasks)  # ❌ Conflict!
```

### Semaphore pour contrôle concurrence
```python
semaphore = asyncio.Semaphore(max_concurrent)

async def fetch_with_limit(url):
    async with semaphore:
        return await http_client.get(url)

results = await asyncio.gather(*[fetch_with_limit(url) for url in urls])
```

---

## 🔗 Ressources

- [AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
- [SQLAlchemy Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Async](https://fastapi.tiangolo.com/async/)

---

## 📞 Contact

Pour questions/contributions sur V3 :
- Issues GitHub: [tag:v3-async]
- Documentation: `.claude/docs/`
- Tests: `projetV3/tests/`

**Maintenu par:** Équipe MyWebIntelligence
**Dernière mise à jour:** 19 octobre 2025
