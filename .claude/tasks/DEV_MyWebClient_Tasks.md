# Plan d'Intégration MyWebClient + MyWebIntelligence API

**Date :** 2026-02-16
**Objectif :** Unifier l'interface d'exploration (MyWebClient) avec le moteur de crawl/export (API) et intégrer une visualisation graphe réseau.

---

## 1. Diagnostic : Pourquoi rien ne s'intègre

### Deux systèmes isolés

```
┌─────────────────────────┐         ┌──────────────────────────┐
│     MyWebClient         │         │  MyWebIntelligenceAPI    │
│  (legacy, autonome)     │         │  (backend, sans UI)      │
│                         │         │                          │
│  React 16 + Express     │   ??    │  FastAPI + Celery         │
│  SQLite locale     ────────────── │  PostgreSQL              │
│                         │ AUCUN   │                          │
│  Exploration, tags,     │  LIEN   │  Crawl, export GEXF,    │
│  filtres, annotation    │         │  NLP, LLM, SEO          │
│                         │         │                          │
│  PAS de graphe          │         │  PAS d'interface         │
└─────────────────────────┘         └──────────────────────────┘

        client-v2/ (React 18, Vite)
        ├── Connecté à l'API ✓
        ├── CRUD Lands/Expressions ✓
        ├── Export panel ✓
        ├── Operations panel ✓
        ├── Tags basiques ✓
        ├── Annotation texte ✗
        ├── Graphe réseau ✗
        └── Parité legacy ✗ (partielle)
```

### Les ruptures concrètes

| Capacité | Legacy Client | API | client-v2 | Intégré ? |
|----------|--------------|-----|-----------|-----------|
| Base de données | SQLite | PostgreSQL | PostgreSQL (via API) | Legacy isolé |
| Lister/filtrer expressions | Oui | Oui | Oui | client-v2 OK |
| Navigation prev/next | Oui | Non exposé | Non | **Manque** |
| Tags hiérarchiques (drag-drop) | Oui (react-sortable-tree) | CRUD basique | CRUD basique | **Manque drag-drop** |
| Annotation de texte (tagging spans) | Oui (from_char/to_char) | tagged_content API | Non implémenté | **Manque** |
| Édition markdown (readable) | Oui (marked) | readable via crawl | Partiel | **Manque éditeur** |
| Suppression media | Oui | Non exposé | Non | **Manque** |
| Crawl | Non | Oui (Celery) | Oui (lance le job) | client-v2 OK |
| Export GEXF/CSV | Non | Oui (14 formats) | Oui (panneau export) | client-v2 OK |
| Visualisation graphe | **Non** | **Non** | **Non** | **NULLE PART** |
| Operations pipeline | Non | Oui (12 ops) | Oui | client-v2 OK |
| Admin utilisateurs | Non | Oui | Oui | client-v2 OK |

### Conclusion du diagnostic

**client-v2 est la bonne base** : il est déjà connecté à l'API, moderne (React 18 + Vite), et couvre ~70% des fonctionnalités. Il faut :
1. Combler les fonctionnalités manquantes du legacy
2. Ajouter la visualisation graphe réseau
3. Abandonner le legacy client et sa SQLite

---

## 2. Plan de travail

### Phase 1 — Visualisation Graphe Réseau (priorité haute)

C'est le manque le plus critique : l'API produit des GEXF mais aucune interface ne les affiche.

#### 1.1 Choisir la librairie de visualisation

| Librairie | Avantages | Inconvénients |
|-----------|-----------|---------------|
| **Sigma.js v2** | Léger, performant (WebGL), conçu pour GEXF, API moderne | Moins de layouts intégrés |
| Cytoscape.js | Riche en layouts, bien documenté | Plus lourd, pas natif GEXF |
| D3.js (force) | Très flexible, écosystème large | Bas niveau, performances limitées sur grands graphes |
| vis-network | Simple d'utilisation | Moins performant, projet moins actif |

**Recommandation : Sigma.js v2 + Graphology**
- `graphology` : structure de données graphe en JS
- `graphology-gexf` : parsing natif des fichiers GEXF exportés par l'API
- `sigma` : rendu WebGL haute performance
- `graphology-layout-forceatlas2` : layout standard pour graphes web

#### 1.2 Créer le composant GraphViewer

**Fichier :** `client-v2/src/features/graph/GraphViewer.jsx`

**Fonctionnalités :**
- Charger un GEXF depuis l'API (via export ou endpoint dédié)
- Afficher le graphe avec ForceAtlas2
- Nœuds = expressions (pages) ou domaines selon le type
- Taille des nœuds = relevance
- Couleur des nœuds = domaine ou sentiment
- Arêtes = liens entre expressions (expression_links) ou pseudo-links (similarities)
- Zoom, pan, sélection de nœud
- Clic sur nœud → ouvrir le détail de l'expression
- Filtrage par relevance (synchronisé avec les filtres existants)
- Toggle page-level / domain-level

#### 1.3 Ajouter un endpoint API pour graphe en temps réel

Actuellement l'API ne produit du GEXF que via export asynchrone (Celery). Pour une visualisation interactive, il faut un endpoint synchrone.

**Nouveau endpoint :** `GET /api/v2/lands/{land_id}/graph`

```python
# Retourne les données de graphe en JSON (pas GEXF)
{
  "nodes": [
    {"id": 1, "label": "Page Title", "url": "...", "relevance": 8, "depth": 2,
     "domain": "example.com", "sentiment": 0.7, "size": 8}
  ],
  "edges": [
    {"source": 1, "target": 2, "weight": 0.85, "type": "link|similarity"}
  ],
  "metadata": {
    "node_count": 150,
    "edge_count": 340,
    "type": "page"  // ou "domain"
  }
}
```

**Paramètres :** `?type=page|domain&min_relevance=0&max_depth=10&include_similarities=true`

#### 1.4 Intégrer dans la navigation

**Route :** `/lands/:landId/graph`
**Menu sidebar :** Ajouter "Graphe réseau" avec icône dans la navigation de land

```
Sidebar actuel :              Sidebar intégré :
├── Expressions               ├── Expressions
├── Domaines                   ├── Domaines
├── Tags                       ├── Tags
├── Export                     ├── Graphe réseau  ← NOUVEAU
├── Opérations                 ├── Export
                               ├── Opérations
```

#### 1.5 Interactions graphe ↔ exploration

- Clic sur nœud → panneau latéral avec détail expression
- Double-clic → navigation vers ExpressionDetail
- Sélection multiple → opérations en lot (tag, delete)
- Filtre relevance du graphe synchronisé avec ExpressionExplorer
- Highlight des nœuds par tag (couleur du tag)

**Dépendances npm à installer :**
```bash
cd client-v2
npm install sigma graphology graphology-gexf graphology-layout-forceatlas2 graphology-layout graphology-communities-louvain
```

---

### Phase 2 — Parité fonctionnelle avec le Legacy Client

Fonctionnalités présentes dans le legacy mais absentes de client-v2.

#### 2.1 Annotation de texte (Text Tagging/Spans)

Le legacy permet de sélectionner du texte dans une expression et de lui appliquer un tag avec position (from_char, to_char).

**Composant :** `client-v2/src/features/tags/TextAnnotator.jsx`

**Fonctionnalités :**
- Afficher le contenu readable d'une expression
- L'utilisateur sélectionne du texte → popup pour choisir un tag
- Sauvegarde via `POST /api/v2/tagged-content/` (existe déjà)
- Affichage des annotations existantes (surlignage coloré par tag)
- Suppression d'annotation par clic droit ou bouton
- Vue agrégée : toutes les annotations d'un land par tag

**Intégration :** Ajouter dans `ExpressionDetail.jsx` sous le contenu readable

#### 2.2 Tags hiérarchiques avec Drag-and-Drop

Le legacy utilise `react-sortable-tree` pour organiser les tags en arbre avec drag-drop. client-v2 n'a qu'un CRUD plat.

**Solution :** Remplacer le TagManager par un arbre interactif

**Librairie :** `@dnd-kit/core` + `@dnd-kit/sortable` (moderne, React 18 compatible)
- `react-sortable-tree` est obsolète et incompatible React 18

**Fonctionnalités :**
- Arbre de tags avec indentation visuelle
- Drag-drop pour réorganiser (changer parent, changer ordre)
- Édition inline du nom et couleur
- Ajout de tag enfant
- Suppression avec confirmation
- Synchronisation avec `POST /api/v1/tags/{landId}/tags/`

#### 2.3 Navigation prev/next expression

Le legacy a `GET /api/prev` et `GET /api/next` pour naviguer séquentiellement.

**Option A — Endpoint API :** Ajouter des endpoints prev/next dans v2
**Option B — Côté client :** Utiliser la liste d'expressions déjà chargée pour calculer prev/next

**Recommandation :** Option B (pas de modification API nécessaire)
- Stocker les IDs de la liste courante dans le contexte
- Calculer prev/next à partir de la position dans la liste
- Déjà partiellement implémenté dans ExpressionDetail (flèches de navigation)

#### 2.4 Éditeur Markdown pour le contenu readable

Le legacy a un éditeur markdown inline avec `marked`.

**Solution :** Ajouter un éditeur markdown dans ExpressionDetail

**Librairie :** `react-markdown` + `react-textarea-autosize` (léger)
- Vue lecture : rendu markdown
- Vue édition : textarea avec preview côté à côté
- Sauvegarde via `PUT /api/v2/lands/{landId}/expressions/{id}` (champ readable)

#### 2.5 Suppression de media

Le legacy a `POST /api/deleteMedia`.

**Action :** Ajouter un bouton de suppression sur chaque image dans le carousel media de ExpressionDetail.
- Nécessite soit un endpoint API v2 dédié, soit extension de l'endpoint expression update.

---

### Phase 3 — Améliorations de l'intégration

#### 3.1 Dashboard unifié (page d'accueil)

Remplacer la page d'accueil vide par un vrai dashboard :
- Résumé des lands (nombre, dernière activité)
- Jobs en cours (crawl, export)
- Graphe miniature du dernier land actif
- Raccourcis vers les opérations fréquentes

#### 3.2 Recherche globale

Ajouter une barre de recherche dans le Header :
- Recherche dans les titres d'expressions
- Recherche dans le contenu (si indexé)
- Résultats groupés par land/domaine
- Nécessite un endpoint `GET /api/v2/search?q=...`

#### 3.3 Notifications temps réel (optionnel)

Remplacer le polling des jobs par des Server-Sent Events (SSE) :
- Plus léger que WebSocket
- Notifications de fin de crawl, export, etc.
- Barre de notification dans le Header

#### 3.4 Mode offline / cache local

Pour l'exploration hors connexion :
- Service Worker pour les assets statiques
- IndexedDB pour le cache des expressions consultées
- Synchronisation au retour en ligne

---

### Phase 4 — Abandon du Legacy Client

#### 4.1 Vérification de parité

Checklist avant de retirer le legacy :

- [ ] Toutes les fonctionnalités du Context.js sont couvertes par client-v2
- [ ] L'annotation de texte fonctionne
- [ ] Les tags drag-drop fonctionnent
- [ ] La navigation prev/next fonctionne
- [ ] L'éditeur markdown fonctionne
- [ ] Le graphe réseau est fonctionnel
- [ ] Les raccourcis clavier sont portés
- [ ] L'authentification est complète

#### 4.2 Migration des données SQLite

Si des utilisateurs ont des données dans SQLite :
- Script de migration SQLite → PostgreSQL
- `scripts/migrate_sqlite_to_postgres.py`
- Mapper les tables : land → lands, expression → expressions, etc.
- Préserver les tags, tagged_content, media

#### 4.3 Nettoyage

- Archiver `client/` (legacy React 16)
- Archiver `server/` (legacy Express + SQLite)
- Renommer `client-v2/` → `client/`
- Mettre à jour la documentation

---

## 3. Priorités et ordonnancement

```
Semaine 1-2 : Phase 1.1–1.3
  → Installer Sigma.js, créer GraphViewer, endpoint /graph

Semaine 3 :   Phase 1.4–1.5
  → Intégrer graphe dans navigation, interactions

Semaine 4-5 : Phase 2.1–2.2
  → Annotation texte + Tags drag-drop

Semaine 6 :   Phase 2.3–2.5
  → Navigation prev/next, éditeur markdown, suppression media

Semaine 7 :   Phase 3.1–3.2
  → Dashboard, recherche globale

Semaine 8 :   Phase 4
  → Vérification parité, migration, nettoyage
```

---

## 4. Fichiers à créer / modifier

### Nouveaux fichiers (client-v2)

| Fichier | Phase | Description |
|---------|-------|-------------|
| `src/features/graph/GraphViewer.jsx` | 1.2 | Composant principal de visualisation graphe |
| `src/features/graph/GraphControls.jsx` | 1.2 | Contrôles (zoom, layout, filtres) |
| `src/features/graph/GraphNodePanel.jsx` | 1.5 | Panneau détail au clic sur nœud |
| `src/features/graph/useGraph.js` | 1.2 | Hook de gestion du graphe (chargement, layout) |
| `src/api/graphApi.js` | 1.3 | Client API pour l'endpoint /graph |
| `src/features/tags/TextAnnotator.jsx` | 2.1 | Composant d'annotation de texte |
| `src/features/tags/AnnotationPopup.jsx` | 2.1 | Popup de sélection de tag |
| `src/features/tags/TagTree.jsx` | 2.2 | Arbre de tags avec drag-drop |
| `src/features/expressions/MarkdownEditor.jsx` | 2.4 | Éditeur markdown inline |
| `src/features/dashboard/Dashboard.jsx` | 3.1 | Page d'accueil avec résumé |

### Fichiers à modifier (client-v2)

| Fichier | Phase | Modification |
|---------|-------|-------------|
| `src/App.jsx` | 1.4 | Ajouter route `/lands/:landId/graph` |
| `src/components/Sidebar.jsx` | 1.4 | Ajouter lien "Graphe réseau" |
| `src/features/expressions/ExpressionDetail.jsx` | 2.1, 2.4 | Intégrer TextAnnotator + MarkdownEditor |
| `src/features/tags/TagManager.jsx` | 2.2 | Remplacer par TagTree |
| `src/api/tagsApi.js` | 2.1 | Ajouter méthodes tagged-content |
| `package.json` | 1.2 | Ajouter dépendances (sigma, graphology, dnd-kit) |

### Nouveaux fichiers (API)

| Fichier | Phase | Description |
|---------|-------|-------------|
| `app/api/v2/endpoints/graph.py` | 1.3 | Endpoint GET /graph pour données réseau |
| `app/api/v2/endpoints/search.py` | 3.2 | Endpoint GET /search pour recherche globale |
| `scripts/migrate_sqlite_to_postgres.py` | 4.2 | Script de migration de données |

### Fichiers à modifier (API)

| Fichier | Phase | Modification |
|---------|-------|-------------|
| `app/api/v2/router_v2.py` | 1.3 | Enregistrer le router graph |
| `app/services/export_service_sync.py` | 1.3 | Extraire la logique de construction de graphe en méthode réutilisable |

---

## 5. Dépendances techniques

### client-v2 (npm)

```json
{
  "sigma": "^2.4.0",
  "graphology": "^0.25.4",
  "graphology-gexf": "^0.12.1",
  "graphology-layout-forceatlas2": "^0.10.1",
  "graphology-communities-louvain": "^2.0.1",
  "@dnd-kit/core": "^6.1.0",
  "@dnd-kit/sortable": "^8.0.0",
  "react-markdown": "^9.0.1",
  "react-textarea-autosize": "^8.5.3"
}
```

### API (pip) — déjà installé

- `networkx` (déjà dans requirements.txt)
- `python-igraph` (déjà dans requirements.txt)
- Pas de nouvelles dépendances nécessaires côté API

---

## 6. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Performances graphe sur grands lands (>5000 nœuds) | Lenteur, gel UI | Pagination côté API, WebGL (Sigma.js), agrégation par domaine |
| Perte de données SQLite legacy | Données utilisateur perdues | Script de migration + documentation |
| Incompatibilité react-sortable-tree / React 18 | Crash | Utiliser @dnd-kit (natif React 18) |
| Endpoint /graph lent sur grosses bases | Timeout API | Cache Redis, limite de nœuds, lazy loading |
| Scope creep sur le dashboard | Retard | MVP minimal : stats + mini-graphe |

---

## 7. Critères de succès

1. **Graphe fonctionnel** : Un utilisateur peut voir le réseau de pages/domaines d'un land, zoomer, cliquer sur un nœud et voir ses détails
2. **Annotation texte** : Un utilisateur peut surligner du texte, appliquer un tag, et retrouver ses annotations
3. **Tags hiérarchiques** : Un utilisateur peut organiser ses tags par drag-drop comme dans le legacy
4. **Zéro SQLite** : Plus aucune dépendance à SQLite, tout passe par l'API PostgreSQL
5. **Un seul client** : `client-v2/` est le seul point d'entrée utilisateur
