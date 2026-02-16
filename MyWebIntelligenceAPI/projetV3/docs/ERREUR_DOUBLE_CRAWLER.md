# 🔴 ERREUR FRÉQUENTE : Résidus de Double Crawler

**Date**: 20 octobre 2025  
**Gravité**: 🔴 **CRITIQUE** – bloque la V2 si l'ancien code parallèle réapparaît

---

## ❌ Le problème désormais

Depuis la V2, MyWebIntelligence n'utilise **qu'un seul moteur de crawl** :  
`MyWebIntelligenceAPI/app/core/crawler_engine_sync.py`

Tout fragment de code, documentation ou script qui tente encore d'appeler un ancien moteur parallèle doit être supprimé. La majorité des bugs signalés depuis la migration provenaient de références oubliées à l'ancien module.

---

## 🏗️ Architecture actuelle

```
┌────────────────────────────────────────────┐
│  API FastAPI + Workers Celery (SYNC)       │
│      └─ crawler_engine_sync.py             │
│            └─ Source unique de vérité      │
└────────────────────────────────────────────┘
```

- Plus d'appel à `crawler_engine.py` (supprimé)  
- Plus de stratégie « double moteur »  
- Toutes les routes REST, tâches Celery et scripts internes doivent déléguer au même module synchrone.

---

## ✅ Checklist obligatoire avant merge

```bash
# Vérifier qu'il ne reste qu'un moteur utilisé
rg "crawler_engine" MyWebIntelligenceAPI/app -g"*.py"
```

- [ ] Aucun import `crawler_engine` (ancienne version parallélisée)  
- [ ] Les tests d'intégration ciblent `crawler_engine_sync.SyncCrawlerEngine`  
- [ ] Les tâches Celery et jobs CLI appellent la même classe  
- [ ] Les scripts de réparation (`scripts/`) n'exécutent qu'un seul moteur

---

## 🔍 Comment détecter un résidu de l'ancien moteur

1. **Imports** : `from app.core import crawler_engine` → à supprimer immédiatement.  
2. **Nom de classe** : toute mention d'un moteur « parallèle » ou « multi » signale un reliquat à effacer.  
3. **Tests** : toute fixture héritée du moteur parallèle doit être réécrite pour instancier uniquement `SyncCrawlerEngine`.

### Commandes rapides

```bash
rg "crawler_engine" -g"*.py" app/
rg "parallel" -g"*.py" app/
rg "multi crawler" -g"*.md" .claude/
```

---

## 🧹 Plan d'assainissement

1. **Supprimer** tout module ou dossier portant encore une référence explicite à l'ancien moteur parallèle (`parallel`, `dual_crawler`, `double_crawler`).  
2. **Réviser** la configuration Celery : chaque tâche doit instancier `SyncCrawlerEngine`.  
3. **Rejouer** les tests métiers : `tests/test-crawl-simple.sh` et suites Pytest liées aux crawls.  
4. **Mettre à jour** la documentation : pointer vers ce fichier et vers `AGENTS.md` section _Crawler Sync only_.

---

## 📦 Livrables attendus après nettoyage

- ✅ Codebase sans import de l'ancien moteur  
- ✅ Scripts de débogage mis à jour  
- ✅ Guides de test (`README.md`, quickstarts) réécrits pour l'unique moteur  
- ✅ Nouveaux tickets ouverts si un comportement dépendait du parallélisme supprimé

---

## 🚨 Signaux d'alerte en production

- Croissance d'erreurs `ModuleNotFoundError: crawler_engine`  
- Tâches Celery bloquées car elles attendent une coroutine  
- Présence de champs hérités du mode parallèle ou d'options « mode parallèle » dans les payloads API

Sur détection d'un de ces signaux : rollback immédiat et purge des reliquats.

---

## 📚 Références utiles

- `.claude/AGENTS.md` — section « Crawler V2 : sync only »  
- `MyWebIntelligenceAPI/app/core/crawler_engine_sync.py` — implémentation unique  
- `tests/test-crawl-simple.sh` — script de validation de bout en bout
