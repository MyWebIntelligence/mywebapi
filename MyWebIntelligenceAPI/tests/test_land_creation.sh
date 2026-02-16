#!/bin/bash

# Get token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "Token: ${TOKEN:0:20}..."

# Test land creation
echo ""
echo "Creating land..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"TestLand$(date +%s)\",\"description\":\"Test land\",\"words\":[\"test\"]}")

echo "Response:"
echo "$RESPONSE" | jq '.'
