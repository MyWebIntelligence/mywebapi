#!/bin/bash

TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r '.access_token')

echo "Checking land 21 expressions..."
curl -s -X GET "http://localhost:8000/api/v1/lands/21/expressions?page=1&per_page=1" \
  -H "Authorization: Bearer $TOKEN" | jq '.items[0] | {
    id,
    url,
    title,
    description: (.description[:100]),
    keywords,
    readable_length: (.readable | length)
  }'
