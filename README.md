# Pulse

Monorepo containing the Pulse frontend and backend services.

## Structure

```
Pulse/
├── api/        # Python backend (uv)
├── web/        # React frontend (bun)
├── docker/     # Dockerfiles + docker-compose
├── docs/       # Architecture docs and runbooks
└── scripts/    # Cross-project dev automation
```

## Getting started

### Prerequisites
- [bun](https://bun.sh/) — frontend package manager
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Docker](https://docs.docker.com/get-docker/) — for running services together

### Run locally

```bash
# Start both services (requires two terminals or use the script)
./scripts/dev.sh

# Or individually:
cd web && bun dev
cd api && uv run fastapi dev
```

### Run with Docker

```bash
docker compose -f docker/docker-compose.yml up
```

## Services

| Service  | Local URL              |
|----------|------------------------|
| Web      | http://localhost:5173  |
| API      | http://localhost:8000  |
