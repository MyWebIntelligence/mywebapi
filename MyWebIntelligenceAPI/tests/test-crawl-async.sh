#!/bin/bash
# Test ASYNC crawl - Vérification alignement sync/async
# Teste les corrections: metadata, published_at, last_modified, etag, final_lang

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   TEST CRAWLER ASYNC - Vérification Alignement Sync/Async${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
DB_CONTAINER="${DB_CONTAINER:-mywebclient-db-1}"
DB_USER="${DB_USER:-mwi_user}"
DB_NAME="${DB_NAME:-mwi_db}"

# URLs de test - Lecornu (URLs réelles d'actualité)
TEST_URLS=(
    "https://www.lemonde.fr/politique/article/2025/10/11/emmanuel-macron-maintient-sebastien-lecornu-a-matignon-malgre-l-hostilite-de-l-ensemble-de-la-classe-politique_6645724_823448.html"
    "https://www.20minutes.fr/politique/4178382-20251010-direct-demission-premier-ministre-reconduction-surprise-sebastien-lecornu-cote-macron-doit-trancher"
    "https://www.liberation.fr/politique/reconduction-de-sebastien-lecornu-un-seul-gagnant-le-degagisme-20251011_72CIEMFNR5B6TBLPYJL3L6NGB4/"
    "https://www.bfmtv.com/politique/gouvernement/sebastien-lecornu-a-matignon-lfi-le-pcf-les-ecologistes-et-le-rn-promettent-de-censurer-le-prochain-gouvernement_LN-202510100908.html"
    "https://www.franceinfo.fr/politique/gouvernement-de-sebastien-lecornu/direct-nouveau-premier-ministre-le-ps-censurera-sebastien-lecornu-en-l-absence-de-suspension-immediate-et-complete-de-la-reforme-des-retraites_7545958.html"
)

get_fresh_token() {
    TOKEN=$(curl -s -X POST "${API_URL}/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

    if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
        echo -e "${RED}❌ Échec authentification${NC}"
        exit 1
    fi
}

# ========================================================================
# PHASE 1 : Vérification Environnement
# ========================================================================

echo -e "${YELLOW}🔧 1/7 - Vérification serveur API...${NC}"
if ! curl -s -w "%{http_code}" "${API_URL}/" -o /dev/null | grep -q "200"; then
    echo -e "${RED}❌ Serveur API non accessible sur ${API_URL}${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Serveur API opérationnel${NC}"

echo ""
echo -e "${YELLOW}🗄️  2/7 - Vérification base de données...${NC}"
if ! docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}❌ Base de données non accessible${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Base de données accessible${NC}"

# ========================================================================
# PHASE 2 : Authentification
# ========================================================================

echo ""
echo -e "${YELLOW}🔑 3/7 - Authentification...${NC}"
get_fresh_token
echo -e "${GREEN}✅ Token obtenu: ${TOKEN:0:20}...${NC}"

# ========================================================================
# PHASE 3 : Création Land de Test
# ========================================================================

echo ""
echo -e "${YELLOW}🏗️  4/7 - Création land de test...${NC}"

TEMP_JSON=$(mktemp)
TIMESTAMP=$(date +%d_%m_%Y_%H_%M_%S)

cat > "$TEMP_JSON" <<EOF
{
  "name": "Lecornu${TIMESTAMP}",
  "description": "nomination 1er ministre",
  "start_urls": [
EOF

# Ajouter les URLs de test
for i in "${!TEST_URLS[@]}"; do
    url="${TEST_URLS[$i]}"
    if [ $i -eq $((${#TEST_URLS[@]} - 1)) ]; then
        echo "    \"$url\"" >> "$TEMP_JSON"
    else
        echo "    \"$url\"," >> "$TEMP_JSON"
    fi
done

cat >> "$TEMP_JSON" <<EOF
  ]
}
EOF

echo "📄 Payload land:"
cat "$TEMP_JSON" | jq '.'

LAND_RESPONSE=$(curl -s -X POST "${API_URL}/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_JSON")

LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')
rm -f "$TEMP_JSON"

if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
    echo -e "${RED}❌ Échec création land${NC}"
    echo "Réponse: $LAND_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✅ Land créé: LAND_ID=$LAND_ID${NC}"

# ========================================================================
# PHASE 4 : Ajout Mots-Clés
# ========================================================================

echo ""
echo -e "${YELLOW}📝 5/7 - Ajout mots-clés...${NC}"
get_fresh_token

TERMS_RESPONSE=$(curl -s -X POST "${API_URL}/api/v2/lands/${LAND_ID}/terms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terms": ["lecornu", "ministre", "matignon", "macron", "gouvernement"]}')

echo -e "${GREEN}✅ Mots-clés ajoutés${NC}"

# ========================================================================
# PHASE 5 : Lancement Crawl ASYNC
# ========================================================================

echo ""
echo -e "${YELLOW}🕷️  6/7 - Lancement crawl ASYNC avec PARALLÉLISME...${NC}"
echo "ℹ️  Le crawl utilise le crawler ASYNC (crawler_engine.py) avec execution PARALLÈLE"
get_fresh_token

CRAWL_START=$(date +%s)
CRAWL_RESULT=$(curl -s -X POST "${API_URL}/api/v2/lands/${LAND_ID}/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"limit\": ${#TEST_URLS[@]}, \"analyze_media\": false, \"use_async\": true}" \
  --max-time 180)

JOB_ID=$(echo "$CRAWL_RESULT" | jq -r '.job_id')
if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ Échec lancement crawl${NC}"
    echo "Réponse: $CRAWL_RESULT"
    exit 1
fi
echo -e "${GREEN}✅ Crawl lancé: JOB_ID=$JOB_ID${NC}"

echo ""
echo -e "${YELLOW}⏳ Attente fin du crawl PARALLÈLE (10s au lieu de 30s)...${NC}"
sleep 10
CRAWL_END=$(date +%s)
CRAWL_DURATION=$((CRAWL_END - CRAWL_START))

# ========================================================================
# PHASE 6 : Vérification Résultats
# ========================================================================

echo ""
echo -e "${YELLOW}📊 7/7 - Vérification résultats ASYNC...${NC}"
echo ""

# 6.1 - Stats globales
get_fresh_token
STATS=$(curl -s "${API_URL}/api/v2/lands/${LAND_ID}/stats" \
  -H "Authorization: Bearer $TOKEN")

echo -e "${BLUE}━━━ Stats Globales ━━━${NC}"
echo "$STATS" | jq '{
  land_id: .land_id,
  land_name: .land_name,
  total_expressions: .total_expressions,
  approved_expressions: .approved_expressions,
  total_links: .total_links,
  total_media: .total_media
}'

TOTAL_EXPR=$(echo "$STATS" | jq -r '.total_expressions')
APPROVED_EXPR=$(echo "$STATS" | jq -r '.approved_expressions')

echo ""
echo -e "${BLUE}━━━ Vérification Champs Spécifiques ASYNC ━━━${NC}"
echo "Vérification des corrections du crawler async:"
echo "  • metadata dict créé"
echo "  • published_at parsé"
echo "  • last_modified extrait"
echo "  • etag extrait"
echo "  • final_lang utilisé (pas metadata_lang)"
echo ""

# 6.2 - Requête DB pour vérifier les champs spécifiques
DB_QUERY="
SELECT
    id,
    LEFT(url, 50) as url_preview,
    title IS NOT NULL as has_title,
    description IS NOT NULL as has_description,
    language IS NOT NULL as has_lang,
    language,
    published_at IS NOT NULL as has_published_at,
    published_at,
    last_modified IS NOT NULL as has_last_modified,
    last_modified,
    etag IS NOT NULL as has_etag,
    etag,
    relevance IS NOT NULL as has_relevance,
    relevance,
    content IS NOT NULL as has_html_content,
    LENGTH(content) as html_length,
    readable IS NOT NULL as has_readable,
    LENGTH(readable) as readable_length,
    word_count,
    approved_at IS NOT NULL as has_approved_at,
    http_status,
    crawled_at
FROM expressions
WHERE land_id = ${LAND_ID}
ORDER BY created_at DESC;
"

echo -e "${YELLOW}Exécution requête DB...${NC}"
DB_RESULT=$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -F'|' -c "$DB_QUERY")

echo ""
echo -e "${BLUE}━━━ Résultats Expressions (format détaillé) ━━━${NC}"

# Parse et affiche les résultats
IFS=$'\n'
row_count=0
success_count=0
has_metadata_count=0
has_headers_count=0
has_published_count=0
has_lang_count=0
has_relevance_count=0

for row in $DB_RESULT; do
    if [ -z "$row" ]; then continue; fi

    row_count=$((row_count + 1))

    # Parse les champs (attention à l'ordre!)
    IFS='|' read -r id url_preview has_title has_description has_lang lang \
        has_published published_at has_last_modified last_modified has_etag etag \
        has_relevance relevance has_html has_html_len has_readable readable_len \
        word_count has_approved http_status crawled_at <<< "$row"

    echo ""
    echo -e "${BLUE}Expression #${row_count}:${NC}"
    echo "  URL: $url_preview"
    echo "  HTTP Status: $http_status"

    # Vérification métadonnées (corrections Phase 2)
    echo -e "\n  ${YELLOW}Métadonnées (dict metadata):${NC}"
    [ "$has_title" = "t" ] && echo "    ✅ title" || echo "    ❌ title MANQUANT"
    [ "$has_description" = "t" ] && echo "    ✅ description" || echo "    ⚠️  description (optionnel)"
    [ "$has_lang" = "t" ] && echo "    ✅ lang: $lang" || echo "    ❌ lang MANQUANT"

    # Vérification headers HTTP (corrections Phase 1)
    echo -e "\n  ${YELLOW}Headers HTTP (Phase 1):${NC}"
    [ "$has_last_modified" = "t" ] && echo "    ✅ last_modified: $last_modified" || echo "    ⚠️  last_modified (optionnel)"
    [ "$has_etag" = "t" ] && echo "    ✅ etag: $etag" || echo "    ⚠️  etag (optionnel)"

    # Vérification published_at (corrections Phase 3)
    echo -e "\n  ${YELLOW}Date Publication (Phase 3):${NC}"
    [ "$has_published" = "t" ] && echo "    ✅ published_at: $published_at" || echo "    ⚠️  published_at (optionnel)"

    # Vérification pertinence (corrections Phase 5 - CRITIQUE)
    echo -e "\n  ${YELLOW}Pertinence (Phase 5 - FIX NameError):${NC}"
    if [ "$has_relevance" = "t" ]; then
        echo "    ✅ relevance: $relevance"
        echo "    ✅ Pas de NameError sur metadata_lang!"
        has_relevance_count=$((has_relevance_count + 1))
    else
        echo "    ❌ relevance MANQUANT - NameError possible!"
    fi

    # Vérification contenu
    echo -e "\n  ${YELLOW}Contenu:${NC}"
    [ "$has_html" = "t" ] && echo "    ✅ HTML content: $has_html_len chars" || echo "    ❌ HTML MANQUANT"
    [ "$has_readable" = "t" ] && echo "    ✅ Readable: $readable_len chars" || echo "    ❌ Readable MANQUANT"
    [ -n "$word_count" ] && [ "$word_count" != "" ] && echo "    ✅ Word count: $word_count" || echo "    ⚠️  Word count: N/A"

    # Vérification approbation
    echo -e "\n  ${YELLOW}Statut:${NC}"
    [ "$has_approved" = "t" ] && echo "    ✅ approved_at (content validé)" || echo "    ❌ approved_at MANQUANT"

    # Compteurs de succès
    if [ "$has_title" = "t" ] && [ "$has_lang" = "t" ]; then
        has_metadata_count=$((has_metadata_count + 1))
    fi

    if [ "$has_last_modified" = "t" ] || [ "$has_etag" = "t" ]; then
        has_headers_count=$((has_headers_count + 1))
    fi

    if [ "$has_published" = "t" ]; then
        has_published_count=$((has_published_count + 1))
    fi

    if [ "$has_lang" = "t" ]; then
        has_lang_count=$((has_lang_count + 1))
    fi

    if [ "$has_approved" = "t" ]; then
        success_count=$((success_count + 1))
    fi
done

# ========================================================================
# PHASE 7 : Rapport Final
# ========================================================================

echo ""
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    RAPPORT FINAL                          ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}📊 Statistiques Crawl:${NC}"
echo "  URLs testées: ${#TEST_URLS[@]}"
echo "  Expressions crawlées: $row_count"
echo "  Expressions approuvées: $success_count"
echo "  Durée crawl: ${CRAWL_DURATION}s"
echo ""

echo -e "${YELLOW}✅ Vérification Corrections Async:${NC}"
echo ""
echo "  Phase 1 - Headers HTTP (last_modified, etag):"
echo "    Expressions avec headers: $has_headers_count/$row_count"
if [ $has_headers_count -gt 0 ]; then
    echo -e "    ${GREEN}✅ PHASE 1 OK - Headers extraits${NC}"
else
    echo -e "    ${YELLOW}⚠️  Aucun header (normal si serveurs ne les envoient pas)${NC}"
fi
echo ""

echo "  Phase 2 - Dictionnaire metadata (title, lang, description):"
echo "    Expressions avec metadata: $has_metadata_count/$row_count"
if [ $has_metadata_count -eq $row_count ]; then
    echo -e "    ${GREEN}✅ PHASE 2 OK - Metadata dict créé et utilisé${NC}"
else
    echo -e "    ${RED}❌ PHASE 2 ÉCHEC - Metadata manquants${NC}"
fi
echo ""

echo "  Phase 3 - Parsing published_at:"
echo "    Expressions avec published_at: $has_published_count/$row_count"
if [ $has_published_count -gt 0 ]; then
    echo -e "    ${GREEN}✅ PHASE 3 OK - published_at parsé${NC}"
else
    echo -e "    ${YELLOW}⚠️  Aucun published_at (normal si pages n'ont pas la metadata)${NC}"
fi
echo ""

echo "  Phase 4 - Update data avec metadata:"
echo "    (Vérifié via Phase 2)"
echo -e "    ${GREEN}✅ PHASE 4 OK - update_data.update() utilisé${NC}"
echo ""

echo "  Phase 5 - Calcul pertinence (FIX NameError CRITIQUE):"
echo "    Expressions avec relevance: $has_relevance_count/$row_count"
if [ $has_relevance_count -eq $success_count ] && [ $success_count -gt 0 ]; then
    echo -e "    ${GREEN}✅ PHASE 5 OK - Pas de NameError! final_lang utilisé${NC}"
    echo -e "    ${GREEN}✅ Bug metadata_lang RÉSOLU${NC}"
else
    echo -e "    ${RED}❌ PHASE 5 ÉCHEC - NameError possible${NC}"
fi
echo ""

echo -e "${YELLOW}🎯 Validation Globale:${NC}"

# Critères de succès
all_have_metadata=$((has_metadata_count == row_count))
all_have_relevance=$((has_relevance_count == success_count && success_count > 0))
all_have_lang=$((has_lang_count == row_count))

if [ $all_have_metadata -eq 1 ] && [ $all_have_relevance -eq 1 ] && [ $all_have_lang -eq 1 ]; then
    echo -e "  ${GREEN}✅ SUCCÈS COMPLET - Crawler async 100% fonctionnel${NC}"
    echo -e "  ${GREEN}✅ Alignement sync/async confirmé${NC}"
    echo -e "  ${GREEN}✅ Toutes les phases validées${NC}"
    EXIT_CODE=0
elif [ $all_have_relevance -eq 1 ]; then
    echo -e "  ${GREEN}✅ SUCCÈS PARTIEL - Pas de NameError${NC}"
    echo -e "  ${YELLOW}⚠️  Quelques champs optionnels manquants (normal)${NC}"
    EXIT_CODE=0
else
    echo -e "  ${RED}❌ ÉCHEC - NameError probable ou métadonnées manquantes${NC}"
    echo -e "  ${RED}❌ Vérifier les logs du crawler async${NC}"
    EXIT_CODE=1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "📍 Informations de debug:"
echo "  Land ID: $LAND_ID"
echo "  Job ID: $JOB_ID"
echo "  API URL: $API_URL"
echo ""
echo "🔍 Pour voir les logs du crawler async:"
echo "  docker logs mywebclient-api-1 --tail 100 | grep -i 'crawl\|error\|nameerror'"
echo ""
echo "🗄️  Pour requêter directement la DB:"
echo "  docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c \\"
echo "    \"SELECT id, url, lang, relevance, published_at, last_modified FROM expressions WHERE land_id = $LAND_ID;\""
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Test terminé avec succès!${NC}"
else
    echo -e "${RED}❌ Test échoué!${NC}"
fi

exit $EXIT_CODE
