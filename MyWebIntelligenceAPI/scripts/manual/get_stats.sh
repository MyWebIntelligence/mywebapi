#!/bin/bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4/stats" | jq
