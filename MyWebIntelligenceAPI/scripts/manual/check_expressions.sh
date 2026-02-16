#!/bin/bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

echo "========== Expressions du Land 4 =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/expressions?page=1&page_size=10" | jq

echo ""
echo "========== Dictionnaire du Land 4 =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/dictionary-stats" | jq

echo ""
echo "========== Domains du Land 4 =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/domains?page=1&page_size=5" | jq
