# Architecture

## Overview

Pulse is a polyglot monorepo. The frontend and backend are independent projects
co-located for shared CI/CD and infrastructure configuration.

## Services

### `web/` — Frontend
- **Runtime**: Bun
- **Framework**: React 19 + Vite
- **Styling**: Tailwind CSS v4 + shadcn/ui
- **Port**: 5173 (dev), served as static files in production

### `api/` — Backend
- **Runtime**: Python 3.13
- **Package manager**: uv
- **Port**: 8000

## Communication

The web frontend communicates with the API over HTTP. In development, the API
URL is configured via the `VITE_API_URL` environment variable.

## Infrastructure

Docker Compose (`docker/docker-compose.yml`) wires the services together for
local end-to-end development and is the basis for production container images.
