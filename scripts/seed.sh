#!/usr/bin/env bash
# Seed the database with synthetic pipeline data.
# Run the API first: ./scripts/dev.sh
set -e

API_URL="${PULSE_API_URL:-http://localhost:8000}"

echo "Seeding database via ${API_URL}/dev/seed ..."
curl -s -X POST "${API_URL}/dev/seed" \
  -H "Content-Type: application/json" \
  | python3 -m json.tool

echo ""
echo "Done."
