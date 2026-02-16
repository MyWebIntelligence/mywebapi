#!/bin/bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" | jq -r .access_token)

echo "========== JOB 11 (Crawl) =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/jobs/11" | jq

echo ""
echo "========== JOB 12 (Media Analysis) =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/jobs/12" | jq

echo ""
echo "========== JOB 13 (Readable Pipeline) =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/jobs/13" | jq

echo ""
echo "========== Land 4 Details =========="
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/lands/4" | jq
