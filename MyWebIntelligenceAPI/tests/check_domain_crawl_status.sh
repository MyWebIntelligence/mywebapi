#!/bin/bash
# Vérifie l'état d'implémentation du Domain Crawl
# et prépare un environnement de test

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
LAND_ID="${1:-}"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Vérification état Domain Crawl${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Vérifier serveur
echo -e "\n${YELLOW}1. Vérification serveur...${NC}"
if curl -s "${API_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Serveur accessible${NC}"
else
    echo -e "${RED}❌ Serveur non accessible: ${API_URL}${NC}"
    exit 1
fi

# 2. Authentification
echo -e "\n${YELLOW}2. Authentification...${NC}"
TOKEN=$(curl -s -X POST "${API_URL}/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Authentification échouée${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Authentifié${NC}"

# 3. Vérifier si l'endpoint domain crawl existe
echo -e "\n${YELLOW}3. Vérification endpoint Domain Crawl...${NC}"

# Essayer l'endpoint
ENDPOINT_CHECK=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/api/v2/domains/stats" \
  -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$ENDPOINT_CHECK" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Endpoint /api/v2/domains/stats existe${NC}"
    DOMAIN_CRAWL_IMPLEMENTED=true
elif [ "$HTTP_CODE" = "404" ]; then
    echo -e "${RED}❌ Endpoint /api/v2/domains/stats n'existe pas (404)${NC}"
    DOMAIN_CRAWL_IMPLEMENTED=false
else
    echo -e "${YELLOW}⚠️  Endpoint retourne HTTP ${HTTP_CODE}${NC}"
    DOMAIN_CRAWL_IMPLEMENTED=false
fi

# 4. Vérifier si la table domains existe
echo -e "\n${YELLOW}4. Vérification table domains en DB...${NC}"

DOMAIN_TABLE_CHECK=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
  "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'domains');" 2>/dev/null || echo "f")

if [ "$DOMAIN_TABLE_CHECK" = " t" ]; then
    echo -e "${GREEN}✅ Table 'domains' existe${NC}"

    # Compter les domaines
    TOTAL_DOMAINS=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
      "SELECT COUNT(*) FROM domains;" 2>/dev/null | xargs)

    echo "   Total domaines en DB: ${TOTAL_DOMAINS}"
else
    echo -e "${RED}❌ Table 'domains' n'existe pas${NC}"
fi

# 5. Si land_id fourni, vérifier ses domaines
if [ -n "$LAND_ID" ]; then
    echo -e "\n${YELLOW}5. Vérification land ${LAND_ID}...${NC}"

    LAND_CHECK=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
      "SELECT name FROM lands WHERE id = ${LAND_ID};" 2>/dev/null)

    if [ -n "$LAND_CHECK" ]; then
        echo -e "${GREEN}✅ Land existe: ${LAND_CHECK}${NC}"

        # Compter domaines du land
        LAND_DOMAINS=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
          "SELECT COUNT(*) FROM domains WHERE land_id = ${LAND_ID};" 2>/dev/null | xargs)

        LAND_UNFETCHED=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
          "SELECT COUNT(*) FROM domains WHERE land_id = ${LAND_ID} AND fetched_at IS NULL;" 2>/dev/null | xargs)

        echo "   Domaines total: ${LAND_DOMAINS}"
        echo "   Non fetchés: ${LAND_UNFETCHED}"

        # Compter expressions et liens
        LAND_EXPRESSIONS=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
          "SELECT COUNT(*) FROM expressions WHERE land_id = ${LAND_ID};" 2>/dev/null | xargs)

        LAND_LINKS=$(docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -t -c \
          "SELECT COUNT(l.*) FROM links l JOIN expressions e ON l.expression_id = e.id WHERE e.land_id = ${LAND_ID};" 2>/dev/null | xargs)

        echo "   Expressions: ${LAND_EXPRESSIONS}"
        echo "   Liens: ${LAND_LINKS}"
    else
        echo -e "${RED}❌ Land ${LAND_ID} n'existe pas${NC}"
    fi
fi

# 6. Résumé et recommandations
echo -e "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📋 RÉSUMÉ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$DOMAIN_CRAWL_IMPLEMENTED" = true ]; then
    echo -e "${GREEN}✅ Domain Crawl est IMPLÉMENTÉ${NC}"
    echo ""
    echo "🚀 Vous pouvez tester maintenant:"
    if [ -n "$LAND_ID" ]; then
        echo "   ./MyWebIntelligenceAPI/tests/test-domain-crawl.sh ${LAND_ID} 5"
    else
        echo "   ./MyWebIntelligenceAPI/tests/test-domain-crawl.sh [land_id] [limit]"
    fi
else
    echo -e "${YELLOW}⚠️  Domain Crawl n'est PAS ENCORE IMPLÉMENTÉ${NC}"
    echo ""
    echo "📚 État actuel:"
    echo "   ✅ Plan de développement créé (.claude/tasks/domaincrawl_dev.md)"
    echo "   ✅ Tests préparés (test-domain-crawl.sh, get_crawled_domains.py)"
    echo "   ❌ Code pas encore implémenté"
    echo ""
    echo "🔧 Pour préparer des domaines de test (en attendant l'implémentation):"
    if [ -n "$LAND_ID" ]; then
        echo "   docker exec mywebintelligenceapi python tests/prepare_test_domains.py ${LAND_ID}"
    else
        echo "   docker exec mywebintelligenceapi python tests/prepare_test_domains.py [land_id]"
    fi
    echo ""
    echo "📖 Prochaines étapes (V2 SYNC UNIQUEMENT):"
    echo "   ⚠️  RAPPEL: V2 = SYNC seulement (pas d'async)"
    echo ""
    echo "   1. Implémenter domain_crawler.py (SYNC pur avec requests)"
    echo "   2. Créer domain_crawl_service.py (Session sync)"
    echo "   3. Ajouter domain_crawl_task.py (Celery)"
    echo "   4. Créer endpoints API (app/api/v2/endpoints/domains.py - sans async def)"
    echo "   5. Lancer les tests"
    echo ""
    echo "   ❌ PAS de domain_crawler_async.py"
    echo "   ❌ PAS de domain_crawler_sync.py"
    echo "   ❌ PAS de AsyncSession, aiohttp, async/await"
    echo ""
    echo "📄 Voir le plan complet V2 SYNC:"
    echo "   cat .claude/tasks/domaincrawl_dev.md"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
