#!/bin/bash
curl -s -X POST "http://localhost:8000/api/v1/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin@example.com&password=changethispassword" > /tmp/auth.json
TOKEN=$(cat /tmp/auth.json | jq -r .access_token)

echo "Checking dictionary-stats endpoint..."
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/dictionary-stats"
echo ""

echo "Checking populate-dictionary endpoint..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/populate-dictionary"
echo ""
