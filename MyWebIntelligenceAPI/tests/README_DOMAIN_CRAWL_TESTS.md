# Tests Domain Crawl

Tests automatisés pour valider le système de crawl de domaines.

## 📁 Fichiers

### 1. `test-domain-crawl.sh`
Script bash end-to-end qui teste le workflow complet du domain crawl.

**Fonctionnalités:**
- ✅ Vérifie l'accessibilité du serveur
- ✅ Authentifie l'utilisateur
- ✅ Crée un land de test (ou utilise un existant)
- ✅ Vérifie les domaines disponibles
- ✅ Lance le crawl des domaines
- ✅ Surveille la progression du job
- ✅ Affiche les statistiques avant/après
- ✅ Récupère les détails du job

### 2. `get_crawled_domains.py`
Script Python pour récupérer et afficher les domaines crawlés.

**Fonctionnalités:**
- ✅ Liste les domaines crawlés d'un land
- ✅ Affiche les métadonnées (titre, description, keywords, http_status, etc.)
- ✅ Montre les statistiques globales
- ✅ Exporte en JSON (optionnel)

---

## 🚀 Utilisation

### Test complet du Domain Crawl

#### Option 1: Créer un nouveau land
```bash
cd MyWebClient
./MyWebIntelligenceAPI/tests/test-domain-crawl.sh
```

#### Option 2: Utiliser un land existant
```bash
./MyWebIntelligenceAPI/tests/test-domain-crawl.sh 69 10
#                                                 │  │
#                                                 │  └─ Limite (nombre de domaines)
#                                                 └──── Land ID
```

#### Variables d'environnement
```bash
# Changer l'URL de l'API
API_URL=http://production.com:8000 ./MyWebIntelligenceAPI/tests/test-domain-crawl.sh
```

---

### Récupérer les domaines crawlés

#### Usage de base
```bash
# Depuis le host
docker exec mywebintelligenceapi python tests/get_crawled_domains.py 69 10

# Depuis le container
python tests/get_crawled_domains.py 69 10
```

#### Options disponibles
```bash
# Avec export JSON
python tests/get_crawled_domains.py 69 10 --json

# Voir seulement les stats
python tests/get_crawled_domains.py 69 --stats

# Combiner les options
python tests/get_crawled_domains.py 69 20 --json --stats
```

---

## 📊 Exemple de sortie

### test-domain-crawl.sh

```
🧪 Test Domain Crawl - 2025-10-19 15:46:23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 1/7 - Vérification serveur...
✅ Serveur accessible

🔑 2/7 - Authentification...
✅ Token: eyJhbGciOiJIUzI1NiIs...

🏗️ 3/7 - Création land de test...
✅ Land créé: LAND_ID=70

📊 4/7 - Vérification domaines disponibles...
   Total domaines: 3
   Non fetchés: 3

🕷️ 5/7 - Lancement Domain Crawl...
✅ Crawl lancé: JOB_ID=71
   Domaines à crawler: 3
   Canal WebSocket: domain_crawl_progress_71

⏳ 6/7 - Attente fin du crawl (max 60s)...
   Progression: 100% (completed)
✅ Crawl terminé avec succès

📊 7/7 - Vérification résultats...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 RÉSULTATS FINAUX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Land ID:              70
Job ID:               71
Statut Job:           completed

Domaines total:       3
Avant crawl:          3 non fetchés
Après crawl:          3 fetchés
Nouveaux fetchés:     3
Statut HTTP moyen:    200.0

Détails du crawl:
{
  "total": 3,
  "processed": 3,
  "success": 3,
  "errors": 0,
  "by_source": {
    "trafilatura": 2,
    "archive_org": 1,
    "http_direct": 0,
    "error": 0
  },
  "start_time": "2025-10-19T15:46:25.123456",
  "end_time": "2025-10-19T15:46:35.654321"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Pour voir les domaines crawlés:
   docker exec mywebintelligenceapi python tests/get_crawled_domains.py 70 10

✅ Test terminé!
```

### get_crawled_domains.py

```
📊 STATISTIQUES
────────────────────────────────────────
Total domaines:       3
Domaines fetchés:     3 (100.0%)
Non fetchés:          0

Succès (200):         2
Erreurs client (4xx): 1
Erreurs serveur (5xx):0
Taux de succès:       66.67%
────────────────────────────────────────

================================================================================
🌐 DOMAINES CRAWLÉS - Land ID: 70
================================================================================

1. ✅ www.example.com
   ──────────────────────────────────────────────────────────────────────
   ID:              123
   Titre:           Example Domain
   Description:     Example Domain. This domain is for use in illustrative...
   Mots-clés:       example, domain, test
   Langue:          en
   Statut HTTP:     200
   Crawlé le:       2025-10-19 15:46:28
   Dernier crawl:   2025-10-19 15:46:28
   Source:          trafilatura
   Durée fetch:     1523 ms

2. ✅ www.wikipedia.org
   ──────────────────────────────────────────────────────────────────────
   ID:              124
   Titre:           Wikipedia, the free encyclopedia
   Description:     Wikipedia is a free online encyclopedia, created and...
   Mots-clés:       wikipedia, encyclopedia, free
   Langue:          en
   Statut HTTP:     200
   Crawlé le:       2025-10-19 15:46:32
   Dernier crawl:   2025-10-19 15:46:32
   Source:          trafilatura
   Durée fetch:     3421 ms

3. ❌ github.com
   ──────────────────────────────────────────────────────────────────────
   ID:              125
   Titre:           GitHub: Let's build from here
   Description:     GitHub is where over 100 million developers shape...
   Mots-clés:       github, development, code
   Langue:          en
   Statut HTTP:     403
   Crawlé le:       2025-10-19 15:46:34
   Dernier crawl:   2025-10-19 15:46:34
   Source:          archive_org
   Durée fetch:     2134 ms
   ⚠️  Erreur:       ERR_HTTP_403 - Forbidden

================================================================================
Total affiché: 3 domaine(s)
================================================================================

✅ Successfully retrieved 3 domain(s).

💡 Options supplémentaires:
   --json, -j     Exporter en JSON
   --stats, -s    Afficher uniquement les stats

   Exemple: python tests/get_crawled_domains.py 70 10 --json
```

---

## 🧪 Scénarios de test

### 1. Test basic - Nouveau land
```bash
# Crée un land avec 3 domaines et les crawle
./tests/test-domain-crawl.sh
```

### 2. Test avec limite
```bash
# Crawl seulement 5 domaines d'un land existant
./tests/test-domain-crawl.sh 15 5
```

### 3. Test de performance
```bash
# Crawl 50 domaines et mesure le temps
time ./tests/test-domain-crawl.sh 15 50
```

### 4. Vérification après crawl
```bash
# 1. Lancer le crawl
./tests/test-domain-crawl.sh 69 10

# 2. Vérifier les domaines crawlés
docker exec mywebintelligenceapi python tests/get_crawled_domains.py 69 10

# 3. Exporter en JSON
docker exec mywebintelligenceapi python tests/get_crawled_domains.py 69 10 --json

# 4. Vérifier le fichier JSON
cat domains_land69_*.json | jq '.[] | {name, title, http_status}'
```

### 5. Debug - Vérifier les logs
```bash
# Logs Celery pendant le crawl
docker logs mywebclient-celery_worker-1 --tail=100 -f

# Logs API
docker logs mywebintelligenceapi --tail=100 -f

# Vérifier DB directement
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT name, title, http_status, fetched_at FROM domains WHERE land_id = 69 ORDER BY fetched_at DESC LIMIT 10;"
```

---

## ✅ Checklist de validation

Avant de considérer le domain crawl comme fonctionnel, vérifiez:

- [ ] Le script `test-domain-crawl.sh` se termine avec succès
- [ ] Le job passe à `completed` (pas `failed`)
- [ ] Au moins 80% des domaines ont `http_status = 200`
- [ ] Tous les domaines ont `fetched_at` défini
- [ ] Les champs `title`, `description`, `language` sont remplis
- [ ] Les métadonnées `source_method` sont correctes (trafilatura/archive_org/http_direct)
- [ ] Les erreurs ont des codes `ERR_*` appropriés
- [ ] Le script `get_crawled_domains.py` affiche correctement les données
- [ ] Les stats correspondent aux résultats attendus
- [ ] Les logs Celery ne montrent pas d'erreurs critiques

---

## 🐛 Troubleshooting

### Problème: "Aucun domaine à crawler"
**Solution:** Le land n'a pas de domaines non-fetchés
```bash
# Vérifier les domaines du land
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT COUNT(*) as total, COUNT(fetched_at) as fetched FROM domains WHERE land_id = 69;"

# Réinitialiser fetched_at si besoin (pour tests seulement!)
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "UPDATE domains SET fetched_at = NULL WHERE land_id = 69;"
```

### Problème: "Job timeout"
**Solution:** Augmentez le timeout ou vérifiez les workers Celery
```bash
# Vérifier les workers
docker ps | grep celery

# Voir les logs des workers
docker logs mywebclient-celery_worker-1 --tail=50

# Relancer les workers si besoin
docker restart mywebclient-celery_worker-1
```

### Problème: "Authentification échouée"
**Solution:** Vérifiez les credentials
```bash
# Vérifier que l'utilisateur admin existe
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT email FROM users WHERE email = 'admin@example.com';"

# Si nécessaire, créer l'utilisateur admin via l'API ou Alembic
```

### Problème: "Tous les domaines échouent (http_status = 0)"
**Solution:** Problème réseau ou Trafilatura
```bash
# Test connexion depuis le container
docker exec mywebintelligenceapi curl -I https://www.example.com

# Vérifier les dépendances
docker exec mywebintelligenceapi pip list | grep -E "trafilatura|aiohttp|beautifulsoup4"

# Voir les logs détaillés
docker logs mywebclient-celery_worker-1 | grep -i "domain"
```

---

## 📚 Références

- [Plan de développement Domain Crawl](../../.claude/tasks/domaincrawl_dev.md)
- [Architecture générale](.../../.claude/system/Architecture.md)
- [Guide des agents](.../../.claude/AGENTS.md)

---

**Auteur:** MyWebIntelligence Team
**Dernière mise à jour:** 2025-10-19
**Version:** 1.0
