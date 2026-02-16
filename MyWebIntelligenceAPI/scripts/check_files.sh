#!/bin/bash
# Script de vérification rapide de la présence des fichiers modifiés

echo "============================================================"
echo "🔧 VÉRIFICATION DES FICHIERS MODIFIÉS"
echo "============================================================"

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $2"
        return 0
    else
        echo -e "${RED}❌${NC} $2"
        return 1
    fi
}

check_function() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $3"
        return 0
    else
        echo -e "${RED}❌${NC} $3"
        return 1
    fi
}

echo ""
echo "📁 Fichiers principaux modifiés:"
echo "============================================================"
check_file "app/core/content_extractor.py" "content_extractor.py"
check_file "app/core/crawler_engine.py" "crawler_engine.py"
check_file "app/schemas/expression.py" "expression.py"

echo ""
echo "🔧 Nouvelles fonctions dans content_extractor.py:"
echo "============================================================"
check_function "app/core/content_extractor.py" "def resolve_url" "resolve_url()"
check_function "app/core/content_extractor.py" "def enrich_markdown_with_media" "enrich_markdown_with_media()"
check_function "app/core/content_extractor.py" "def extract_md_links" "extract_md_links()"
check_function "app/core/content_extractor.py" "output_format='markdown'" "Trafilatura avec output_format='markdown'"
check_function "app/core/content_extractor.py" "include_links=True" "Trafilatura avec include_links=True"
check_function "app/core/content_extractor.py" "include_images=True" "Trafilatura avec include_images=True"
check_function "app/core/content_extractor.py" "trafilatura.fetch_url" "Archive.org avec trafilatura.fetch_url"

echo ""
echo "🔧 Nouvelles méthodes dans crawler_engine.py:"
echo "============================================================"
check_function "app/core/crawler_engine.py" "def _create_links_from_markdown" "_create_links_from_markdown()"
check_function "app/core/crawler_engine.py" "def _save_media_from_list" "_save_media_from_list()"
check_function "app/core/crawler_engine.py" '"content":' 'Persistance du champ content'
check_function "app/core/crawler_engine.py" 'str(http_status_code)' 'http_status en string'

echo ""
echo "🔧 Modifications dans expression.py:"
echo "============================================================"
check_function "app/schemas/expression.py" "content: Optional\[str\]" "Champ content ajouté"
check_function "app/schemas/expression.py" "language: Optional\[str\]" "Champ language ajouté"

echo ""
echo "📄 Fichiers de tests et documentation:"
echo "============================================================"
check_file "tests/test_legacy_parity.py" "test_legacy_parity.py"
check_file "../.claude/TRANSFERT_API_CRAWL.md" "TRANSFERT_API_CRAWL.md (mis à jour)"
check_file "../.claude/CORRECTIONS_PARITÉ_LEGACY.md" "CORRECTIONS_PARITÉ_LEGACY.md"

echo ""
echo "============================================================"
echo "✅ Vérification terminée !"
echo ""
echo "Prochaines étapes:"
echo "  1. Installer les dépendances: pip install -r requirements.txt"
echo "  2. Exécuter les tests: pytest tests/test_legacy_parity.py -v"
echo "  3. Tester sur un land: curl http://localhost:8000/api/lands/{land_id}/crawl -X POST"
echo "============================================================"
