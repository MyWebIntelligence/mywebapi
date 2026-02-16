#!/bin/bash
# Test end-to-end du Domain Crawl
# Usage: ./tests/test-domain-crawl.sh [land_id] [limit]

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
LAND_ID="${1:-}"
LIMIT="${2:-10}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Test Domain Crawl - $(date)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Fonction pour afficher une étape
step() {
    echo -e "\n${YELLOW}$1${NC}"
}

# Fonction pour afficher un succès
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Fonction pour afficher une erreur
error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# 1. Vérification serveur
step "🔧 1/7 - Vérification serveur..."
if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
    error "Serveur non accessible: ${API_URL}"
fi
success "Serveur accessible"

# 2. Authentification
step "🔑 2/7 - Authentification..."
TOKEN=$(curl -s -X POST "${API_URL}/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    error "Authentification échouée"
fi
success "Token: ${TOKEN:0:20}..."

# 3. Créer ou utiliser un land existant
if [ -z "$LAND_ID" ]; then
    step "🏗️ 3/7 - Création land de test..."

    LAND_RESPONSE=$(curl -s -X POST "${API_URL}/api/v2/lands/" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"Domain Crawl Test ${TIMESTAMP}\",
        \"description\": \"Test automatique domain crawl\",
        \"start_urls\": [\"https://www.example.com\", \"https://www.wikipedia.org\", \"https://github.com\"]
      }")

    LAND_ID=$(echo "$LAND_RESPONSE" | jq -r '.id')

    if [ "$LAND_ID" = "null" ] || [ -z "$LAND_ID" ]; then
        error "Création land échouée: $LAND_RESPONSE"
    fi
    success "Land créé: LAND_ID=${LAND_ID}"

    # Attendre un peu que les domaines soient créés
    sleep 2
else
    step "🏗️ 3/7 - Utilisation land existant..."
    success "LAND_ID=${LAND_ID}"
fi

# 4. Vérifier les domaines disponibles
step "📊 4/7 - Vérification domaines disponibles..."

STATS_BEFORE=$(curl -s "${API_URL}/api/v2/domains/stats?land_id=${LAND_ID}" \
  -H "Authorization: Bearer $TOKEN")

TOTAL_DOMAINS=$(echo "$STATS_BEFORE" | jq -r '.total_domains // 0')
UNFETCHED_DOMAINS=$(echo "$STATS_BEFORE" | jq -r '.unfetched_domains // 0')

echo "   Total domaines: ${TOTAL_DOMAINS}"
echo "   Non fetchés: ${UNFETCHED_DOMAINS}"

if [ "$UNFETCHED_DOMAINS" -eq "0" ]; then
    echo -e "${YELLOW}⚠️  Aucun domaine à crawler${NC}"
    echo "   Conseil: Créez un nouveau land avec start_urls ou réinitialisez fetched_at"
fi

# 5. Lancer le crawl
step "🕷️ 5/7 - Lancement Domain Crawl..."

CRAWL_RESPONSE=$(curl -s -X POST "${API_URL}/api/v2/domains/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"land_id\": ${LAND_ID},
    \"limit\": ${LIMIT},
    \"only_unfetched\": true
  }")

JOB_ID=$(echo "$CRAWL_RESPONSE" | jq -r '.job_id')
DOMAIN_COUNT=$(echo "$CRAWL_RESPONSE" | jq -r '.domain_count // 0')
WS_CHANNEL=$(echo "$CRAWL_RESPONSE" | jq -r '.ws_channel')

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    error "Lancement crawl échoué: $CRAWL_RESPONSE"
fi

success "Crawl lancé: JOB_ID=${JOB_ID}"
echo "   Domaines à crawler: ${DOMAIN_COUNT}"
echo "   Canal WebSocket: ${WS_CHANNEL}"

# 6. Attendre la fin du job
step "⏳ 6/7 - Attente fin du crawl (max 60s)..."

JOB_STATUS="pending"
WAIT_COUNT=0
MAX_WAIT=30 # 30 * 2s = 60s

while [ "$JOB_STATUS" != "completed" ] && [ "$JOB_STATUS" != "failed" ] && [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 1))

    JOB_INFO=$(curl -s "${API_URL}/api/v2/jobs/${JOB_ID}" \
      -H "Authorization: Bearer $TOKEN")

    JOB_STATUS=$(echo "$JOB_INFO" | jq -r '.status')
    JOB_PROGRESS=$(echo "$JOB_INFO" | jq -r '.progress // 0')

    echo -ne "   Progression: ${JOB_PROGRESS}% (${JOB_STATUS})    \r"
done

echo "" # Nouvelle ligne après la progression

if [ "$JOB_STATUS" = "completed" ]; then
    success "Crawl terminé avec succès"
elif [ "$JOB_STATUS" = "failed" ]; then
    error "Crawl échoué"
else
    echo -e "${YELLOW}⚠️  Timeout - Job toujours en cours${NC}"
fi

# 7. Vérifier les résultats
step "📊 7/7 - Vérification résultats..."

STATS_AFTER=$(curl -s "${API_URL}/api/v2/domains/stats?land_id=${LAND_ID}" \
  -H "Authorization: Bearer $TOKEN")

FETCHED_AFTER=$(echo "$STATS_AFTER" | jq -r '.fetched_domains // 0')
AVG_STATUS=$(echo "$STATS_AFTER" | jq -r '.avg_http_status // 0')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🎯 RÉSULTATS FINAUX${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Land ID:              ${LAND_ID}"
echo "Job ID:               ${JOB_ID}"
echo "Statut Job:           ${JOB_STATUS}"
echo ""
echo "Domaines total:       ${TOTAL_DOMAINS}"
echo "Avant crawl:          ${UNFETCHED_DOMAINS} non fetchés"
echo "Après crawl:          ${FETCHED_AFTER} fetchés"
echo "Nouveaux fetchés:     $((FETCHED_AFTER - (TOTAL_DOMAINS - UNFETCHED_DOMAINS)))"
echo "Statut HTTP moyen:    ${AVG_STATUS}"
echo ""

# Récupérer les détails du job
JOB_RESULT=$(echo "$JOB_INFO" | jq -r '.result_data // {}')
if [ "$JOB_RESULT" != "{}" ] && [ "$JOB_RESULT" != "null" ]; then
    echo "Détails du crawl:"
    echo "$JOB_RESULT" | jq '.'
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 8. Proposer de récupérer les domaines
echo ""
echo -e "${YELLOW}💡 Pour voir les domaines crawlés:${NC}"
echo "   docker exec mywebintelligenceapi python tests/get_crawled_domains.py ${LAND_ID} 10"
echo ""

success "✅ Test terminé!"
