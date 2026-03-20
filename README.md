# Pulse

Pipeline monitoring dashboard with a live-updating flow graph UI.

## Structure

```
Pulse/
├── api/        # Python backend (FastAPI + SQLAlchemy + TimescaleDB)
├── web/        # React frontend (Bun + React Flow + TanStack Query)
├── docker/     # Dockerfiles + docker-compose
├── docs/       # Architecture docs
└── scripts/    # Dev automation
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — for TimescaleDB
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Bun](https://bun.sh/) — JavaScript runtime and package manager

## Getting Started

### 1. Start the database

```bash
docker compose -f docker/docker-compose.yml up timescaledb
```

Wait until you see `database system is ready to accept connections`.

### 2. Start the API

```bash
cd api
PYTHONUTF8=1 uv run uvicorn pulse_api.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Note:** The standard `fastapi dev` command crashes on Windows due to an emoji encoding bug in the CLI. The `PYTHONUTF8=1` env var with uvicorn directly works around it.

### 3. Seed the database

Once the API is running, seed it with synthetic data (3 pipelines, 90 days of run history, pre-baked anomalies):

```bash
curl -X POST http://localhost:8000/dev/seed
```

Or open http://localhost:8000/docs and call `POST /dev/seed` from the Swagger UI.

This only needs to be done once per fresh database. Data persists in the Docker volume.

### 4. Start the frontend

```bash
cd web
bun install
bun dev
```

Open http://localhost:3000 in your browser.

### Run with Docker (all services)

```bash
docker compose -f docker/docker-compose.yml up
```

## Services

| Service     | Local URL              |
|-------------|------------------------|
| Web         | http://localhost:3000   |
| API         | http://localhost:8000   |
| API Docs    | http://localhost:8000/docs |
| TimescaleDB | localhost:5432         |

## Running Tests

```bash
cd api
uv run pytest
```
