#!/usr/bin/env bash
# Start both the API and web dev servers in parallel.
# Usage: ./scripts/dev.sh

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

trap 'kill 0' EXIT

echo "Starting API (http://localhost:8000)..."
(cd "$ROOT/api" && uv run fastapi dev src/pulse_api/main.py) &

echo "Starting web (http://localhost:5173)..."
(cd "$ROOT/web" && bun dev) &

wait
