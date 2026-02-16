# Chaîne de Fallbacks - Pipeline d'Extraction de Contenu

**Version**: API avec amélioration smart extraction
**Date**: 17 octobre 2025

---

## 📊 Schéma de la Chaîne de Fallbacks

```
┌─────────────────────────────────────────────────────────────────┐
│                     DÉBUT EXTRACTION                             │
│                     URL + HTML (optionnel)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │  MÉTHODE 1: TRAFILATURA DIRECT    │
         │  ─────────────────────────────    │
         │  • output_format='markdown'       │
         │  • include_links=True             │
         │  • include_images=True            │
         │  • Enrichissement médias          │
         │  • Extraction liens markdown      │
         └───────────┬───────────────────────┘
                     │
                     │ ✅ Succès (>100 chars)
                     ├──────────────────────────────────────┐
                     │                                      │
                     │ ❌ Échec                             ▼
                     ▼                              ┌──────────────┐
         ┌───────────────────────────────────┐      │   RETOUR     │
         │   MÉTHODE 2: ARCHIVE.ORG          │      │  ✅ SUCCESS  │
         │   ──────────────────────────      │      │              │
         │  • Recherche snapshot Wayback     │      │ source:      │
         │  • trafilatura.fetch_url()        │      │ trafilatura  │
         │  • Extraction markdown + HTML     │      └──────────────┘
         │  • Enrichissement médias          │
         │  • Extraction liens markdown      │
         └───────────┬───────────────────────┘
                     │
                     │ ✅ Succès (>100 chars)
                     ├──────────────────────────────────────┐
                     │                                      │
                     │ ❌ Échec                             ▼
                     ▼                              ┌──────────────┐
         ┌───────────────────────────────────┐      │   RETOUR     │
         │ MÉTHODE 3: BEAUTIFULSOUP          │      │  ✅ SUCCESS  │
         │ ────────────────────────────      │      │              │
         │                                   │      │ source:      │
         │  ┌─────────────────────────────┐ │      │ archive_org  │
         │  │ 3A. SMART EXTRACTION        │ │      └──────────────┘
         │  │ ───────────────────────     │ │
         │  │ • Sélecteurs intelligents   │ │
         │  │   (article, main, .content) │ │
         │  │ • Extraction paragraphes    │ │
         │  │ • Heuristiques Mercury      │ │
         │  └────────┬────────────────────┘ │
         │           │                       │
         │           │ ✅ Succès (>100 chars)
         │           ├────────────────────────────────────┐
         │           │                                    │
         │           │ ❌ Échec                           ▼
         │           ▼                            ┌──────────────┐
         │  ┌─────────────────────────────┐      │   RETOUR     │
         │  │ 3B. BASIC TEXT EXTRACTION   │      │  ✅ SUCCESS  │
         │  │ ─────────────────────────   │      │              │
         │  │ • clean_html(soup)          │      │ source:      │
         │  │ • get_text()                │      │ beautifulsoup│
         │  │ • Texte brut basique        │      │    _smart    │
         │  └────────┬────────────────────┘      └──────────────┘
         │           │                       │
         │           │ ✅ Succès (>100 chars)│
         │           ├─────────────────────────────────────┐
         │           │                                     │
         │           │ ❌ Échec                            ▼
         │           ▼                             ┌──────────────┐
         └───────────────────────────────────┘     │   RETOUR     │
                     │                             │  ✅ SUCCESS  │
                     │                             │              │
                     │                             │ source:      │
                     ▼                             │ beautifulsoup│
         ┌───────────────────────────────────┐     │    _basic    │
         │        ÉCHEC TOTAL                │     └──────────────┘
         │  ────────────────────             │
         │  • readable = None                │
         │  • extraction_source = 'all_failed'│
         └───────────────────────────────────┘
```

---

## 🔍 Détails des Méthodes

### **1. Trafilatura Direct** (Priorité 1)
**Quand**: HTML fourni ou fetch réussi
**Technologie**: Trafilatura avec options markdown
**Sortie**: Markdown enrichi avec médias et liens
**Seuil**: ≥100 caractères
**Avantage**:
- Format markdown structuré
- Liens et images préservés
- Meilleure qualité d'extraction

### **2. Archive.org** (Priorité 2)
**Quand**: Trafilatura échoue OU pas de HTML fourni
**Technologie**: Wayback Machine + Trafilatura
**Sortie**: Markdown enrichi depuis snapshot historique
**Seuil**: ≥100 caractères
**Avantage**:
- Récupère contenu disparu
- Même qualité que méthode 1
- Pipeline complète identique

### **3. BeautifulSoup** (Priorité 3)
**Quand**: Archive.org échoue ou indisponible
**Technologie**: BeautifulSoup avec 2 sous-niveaux
**Sortie**: Texte (smart si possible, basic sinon)
**Seuil**: ≥100 caractères

#### **3A. Smart Extraction** (Amélioration non-legacy)
**Technologie**: Heuristiques de contenu
**Sélecteurs**:
```
article, [role="main"], main, .content, .post-content,
.entry-content, .article-content, .post-body, .story-body,
#content, #main-content, .main-content, .article-body
```
**Avantage**:
- Meilleure extraction que texte brut basique
- Fonctionne sur sites modernes
- Compatible legacy (fallback)

#### **3B. Basic Text Extraction** (Fallback final)
**Technologie**: BeautifulSoup get_text()
**Process**:
1. `clean_html()` - Supprime scripts, styles, nav, footer
2. `get_text()` - Extraction texte brut
**Avantage**:
- Fonctionne toujours
- Dernier recours

---

## ✅ Conformité Legacy

### Ordre des Méthodes
| Position | Legacy (ancien) | API (nouveau) | Statut |
|----------|----------------|---------------|--------|
| 1 | Trafilatura | Trafilatura (markdown) | ✅ Aligné + amélioré |
| 2 | Archive.org | Archive.org (fetch_url) | ✅ Aligné |
| 3 | BeautifulSoup | BeautifulSoup + smart | ✅ Aligné + amélioré |

### Améliorations Non-Régressives
1. **Format markdown** : Legacy utilisait déjà markdown, mais sans `include_links/images` → **Amélioré**
2. **Smart extraction** : Absente du legacy strict, mais **ajoutée comme amélioration du fallback BeautifulSoup** → **Non-régressive**
3. **Enrichissement médias** : Legacy avait enrichissement basique → **Amélioré et systématisé**

---

## 📈 Sources d'Extraction Tracées

Chaque extraction retourne un champ `extraction_source` pour traçabilité :

| Source | Signification | Qualité |
|--------|--------------|---------|
| `trafilatura_direct` | Trafilatura sur HTML fourni | ⭐⭐⭐⭐⭐ |
| `archive_org` | Trafilatura sur snapshot Wayback | ⭐⭐⭐⭐ |
| `beautifulsoup_smart` | Smart extraction avec heuristiques | ⭐⭐⭐ |
| `beautifulsoup_basic` | Texte brut basique | ⭐⭐ |
| `all_failed` | Échec complet | ❌ |

---

## 🎯 Comportement Attendu

### Scénario 1: Article de blog moderne
```
HTML → Trafilatura → ✅ Markdown enrichi (trafilatura_direct)
```

### Scénario 2: Page avec contenu minimal
```
HTML → Trafilatura (échec <100) → Archive.org (pas de snapshot)
     → BeautifulSoup smart → ✅ Texte structuré (beautifulsoup_smart)
```

### Scénario 3: URL obsolète
```
HTML (erreur 404) → Archive.org → ✅ Markdown depuis snapshot 2023 (archive_org)
```

### Scénario 4: Page très simple
```
HTML → Trafilatura (échec) → Archive.org (pas de snapshot)
     → BeautifulSoup smart (échec) → BeautifulSoup basic
     → ✅ Texte brut (beautifulsoup_basic)
```

---

## 💡 Recommandations

### Monitoring
Tracer la distribution des `extraction_source` :
- Si `beautifulsoup_basic` > 10% → Investiguer pourquoi smart échoue
- Si `archive_org` > 30% → Beaucoup de contenu obsolète
- Si `all_failed` > 5% → Problème critique

### Optimisation Future
1. Ajouter timeout adaptatif par méthode
2. Cacher les snapshots Archive.org
3. Améliorer sélecteurs smart extraction selon domaines

---

**Version**: 1.0
**Date**: 17 octobre 2025
**Statut**: ✅ Implémenté et testé
