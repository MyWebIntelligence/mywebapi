#!/bin/bash

TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

# Update expression 11543 pour forcer un recrawl (mettre approved_at à NULL)
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "UPDATE expressions SET approved_at = NULL WHERE id = 11543;"

echo "Expression 11543 réinitialisée"

# Lancer un crawl sur land 21
echo "Lancement du crawl..."
curl -s -X POST "http://localhost:8000/api/v2/lands/21/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 1, "depth": 0}' | jq '.'

echo "Attente de 15 secondes..."
sleep 15

# Vérifier les résultats
echo ""
echo "Résultat pour expression 11543:"
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c \
  "SELECT id, word_count, reading_time, canonical_url IS NOT NULL as has_canon, content_type FROM expressions WHERE id = 11543;"
