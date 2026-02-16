#!/bin/bash

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained: ${TOKEN:0:20}..."
echo ""

# Create the land and capture FULL response
echo "Creating land 'Lecornu202543'..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/lands/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Lecornu202543","description":"Test gilets jaunes","words":["lecornu"]}')

echo ""
echo "Full Response:"
echo "$RESPONSE" | jq '.'

echo ""
echo "Land ID:"
echo "$RESPONSE" | jq -r '.id'

echo ""
echo "Error (if any):"
echo "$RESPONSE" | jq -r '.detail // "No error"'
