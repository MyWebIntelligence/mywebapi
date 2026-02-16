# Alignement Crawler V2 (Sync Only)

**Statut**: Archivé  
**Contexte**: l'ancien plan traitait l'équilibrage entre deux moteurs de crawl. Depuis la V2 nous ne conservons plus qu'un moteur synchrone (`crawler_engine_sync.py`). Les actions de cette page sont donc obsolètes.

## À faire

- Réécrire un plan dédié au moteur unique si une divergence est détectée.  
- Vérifier que tout nouveau ticket mentionnant un moteur parallèle soit fermé ou réorienté.  
- Pointer vers `ERREUR_DOUBLE_CRAWLER.md` pour la checklist anti-régression.

## Historique

Les versions précédentes conservaient deux moteurs distincts. Toute trace de cette architecture doit être supprimée du code, des scripts et de la documentation.

