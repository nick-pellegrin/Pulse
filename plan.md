# Pulse MVP — Architectural Plan

> Status: APPROVED — ready to scaffold.

---

## 1. Tech Stack

### Frontend (web/)

| Choice | Justification |
|---|---|
| **React Flow (`@xyflow/react`)** | Industry-standard for interactive DAG graphs in React. Supports custom nodes/edges, built-in zoom/pan/selection, performant with large graphs. First-class TypeScript support. |
| **TanStack Query (React Query)** | Best-in-class data fetching for non-realtime data (run history, anomaly list, metrics). Handles caching, background refetch, and loading states cleanly. |
| **Zustand** | Lightweight state store for graph UI state (selected node, panel open/closed, filter state). React Flow's own store handles graph topology; Zustand handles application state around it. |
| **Dagre** | Auto-layout algorithm for DAGs. Computes node positions from graph topology. Computed positions are persisted to DB so layout survives page reload. |
| React 19, Tailwind v4, shadcn/ui, Bun | Already in place. No changes. |

### Backend (api/)

| Choice | Justification |
|---|---|
| **SQLAlchemy 2.0 (async)** | Best async ORM for Python. Declarative models generate Alembic migrations automatically. Essential for TimescaleDB hypertable management. |
| **Alembic** | SQLAlchemy's official migration tool. Handles TimescaleDB-specific DDL (hypertable creation) via raw SQL in migration steps. |
| **asyncpg** | Fastest async Postgres driver. Required for SQLAlchemy async with TimescaleDB. |
| **pydantic-settings** | Config management via environment variables. Keeps `DATABASE_URL`, `AGENT_API_KEY`, etc. out of code. |
| **APScheduler** | Background task scheduler for periodic anomaly detection. Runs in-process alongside FastAPI. Simpler than Celery for MVP. |
| FastAPI, uv, ruff, pyright, pytest | Already in place. No changes. |

### Database

| Choice | Justification |
|---|---|
| **TimescaleDB** | Postgres extension — runs as a Postgres-compatible container. `pipeline_runs`, `node_runs`, and `metrics` become hypertables: automatic time-based partitioning, compressed storage, fast range queries. Regular Postgres tables for structural data (pipelines, nodes, edges). One database, two storage paradigms. |
| `timescale/timescaledb-ha` image | Official TimescaleDB Docker image. Drop-in Postgres replacement for docker-compose. |

### Infrastructure

| Choice | Justification |
|---|---|
| **Docker Compose** | Already in place. TimescaleDB service added alongside `api` and `web`. |
| **FastAPI native WebSockets** | FastAPI has built-in WebSocket support. No additional library needed. Server pushes graph state updates to connected clients when node state changes. |

---

## 2. Finalized Architectural Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Live graph updates | **WebSocket** — server pushes state changes to connected frontend clients. FastAPI native WS; custom `ConnectionManager` handles multi-client broadcasting. |
| 2 | Node state storage | **Computed at query time** — `node_state.py` joins `node_runs` + `anomalies` at request/push time. Always fresh, no extra write path. |
| 3 | Synthetic data scope | **Three named pipelines, 90 days of history** — `jaffle-shop-analytics` (12 nodes), `payments-pipeline` (28 nodes), `ml-feature-store` (45 nodes). Includes baked-in failure patterns and anomalies. |
| 4 | TimescaleDB FK constraint | **App-layer referential integrity** — hypertable cross-references (`node_runs.pipeline_run_id`) are logical only. `services/` enforces integrity at write time. |
| 5 | API authentication | **No auth on CRUD endpoints.** `/agent/*` endpoints require `X-Agent-Key` header validated against `AGENT_API_KEY` env var. |

---

## 3. Proposed Directory Structure

Changes from current structure are marked with `← NEW` or `← MODIFIED`.

```
Pulse/
├── .claude/
├── .github/workflows/
│   ├── api.yml
│   └── web.yml
│
├── api/
│   ├── src/pulse_api/
│   │   ├── __init__.py
│   │   ├── main.py                        ← MODIFIED (register routers, lifespan, WS manager)
│   │   ├── config.py                      ← NEW (pydantic-settings: DB_URL, AGENT_API_KEY, etc.)
│   │   ├── database.py                    ← NEW (SQLAlchemy async engine + session factory)
│   │   ├── models/                        ← NEW
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py                (Pipeline, Node, Edge ORM models)
│   │   │   ├── run.py                     (PipelineRun, NodeRun ORM models)
│   │   │   └── metric.py                  (Metric, Anomaly ORM models)
│   │   ├── schemas/                       ← NEW (Pydantic request/response shapes)
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py
│   │   │   ├── run.py
│   │   │   └── metric.py
│   │   ├── routers/                       ← NEW
│   │   │   ├── __init__.py
│   │   │   ├── pipelines.py               (GET /pipelines, GET /pipelines/{id}/graph)
│   │   │   ├── runs.py                    (GET /pipelines/{id}/runs)
│   │   │   ├── metrics.py                 (GET /nodes/{id}/metrics)
│   │   │   ├── anomalies.py               (GET /anomalies, GET /pipelines/{id}/anomalies)
│   │   │   ├── ingest.py                  (POST /ingest/dbt, POST /ingest/webhook)
│   │   │   ├── ws.py                      ← NEW (WS /ws/pipelines/{id}/graph — live push)
│   │   │   └── agent.py                   (GET /agent/state — NanoClaw endpoint, API key protected)
│   │   ├── services/                      ← NEW
│   │   │   ├── __init__.py
│   │   │   ├── anomaly_detector.py        (z-score + rolling average detection)
│   │   │   ├── dbt_parser.py              (parse dbt manifest.json → DB records)
│   │   │   ├── node_state.py              (derive node health state from runs + anomalies)
│   │   │   ├── ws_manager.py              ← NEW (ConnectionManager: broadcast to WS subscribers)
│   │   │   └── synthetic/                 ← NEW
│   │   │       ├── __init__.py
│   │   │       ├── generator.py           (orchestrates full synthetic dataset)
│   │   │       ├── dag_builder.py         (generates realistic DAG topologies)
│   │   │       ├── run_simulator.py       (simulates run history with failure patterns)
│   │   │       └── metric_simulator.py    (generates volume/duration time-series)
│   │   └── py.typed
│   ├── migrations/                        ← NEW (Alembic)
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_main.py
│   │   ├── test_synthetic.py              ← NEW
│   │   └── test_anomaly_detector.py       ← NEW
│   ├── alembic.ini                        ← NEW
│   ├── pyproject.toml                     ← MODIFIED (add new deps)
│   └── uv.lock
│
├── web/
│   ├── src/
│   │   ├── App.tsx                        ← MODIFIED (add /graph route, QueryClientProvider)
│   │   ├── frontend.tsx
│   │   ├── index.ts
│   │   ├── index.html
│   │   ├── index.css
│   │   ├── pages/
│   │   │   ├── Home.tsx                   ← MODIFIED (pipeline list/selector)
│   │   │   ├── Graph.tsx                  ← NEW (main flow graph view)
│   │   │   ├── Insights.tsx               ← MODIFIED (anomaly feed + health metrics)
│   │   │   └── Data.tsx                   ← MODIFIED (raw metrics/runs table)
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── ThemeProvider.tsx
│   │   │   ├── graph/                     ← NEW
│   │   │   │   ├── PipelineGraph.tsx      (React Flow root component)
│   │   │   │   ├── GraphToolbar.tsx       (zoom controls, layout reset, filter)
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── PipelineNode.tsx   (custom node with status color + pulse animation)
│   │   │   │   │   └── NodeStatusBadge.tsx
│   │   │   │   └── edges/
│   │   │   │       └── DataFlowEdge.tsx   (animated edge showing data flow direction)
│   │   │   ├── panels/                    ← NEW
│   │   │   │   ├── NodeDetailPanel.tsx    (slide-in panel: node runs, metrics, anomalies)
│   │   │   │   └── AnomalyFeed.tsx        (live feed of recent anomalies)
│   │   │   └── ui/                        (shadcn — unchanged)
│   │   ├── hooks/                         ← NEW
│   │   │   ├── usePipelineSocket.ts       (manages WS connection, exposes live graph state)
│   │   │   ├── useNodeRuns.ts             (React Query: fetch node run history)
│   │   │   └── useAnomalies.ts            (React Query: fetch anomaly list)
│   │   ├── store/                         ← NEW
│   │   │   └── graphStore.ts              (Zustand: selected node, panel state, WS status, filters)
│   │   ├── lib/
│   │   │   ├── utils.ts
│   │   │   └── api.ts                     ← NEW (typed fetch wrapper, base URL config)
│   │   ├── types/                         ← NEW
│   │   │   └── pipeline.ts                (TypeScript types mirroring API schemas + WS message shapes)
│   │   └── assets/
│   ├── styles/
│   │   ├── globals.css
│   │   ├── design-system.css
│   │   └── graph.css                      ← NEW (pulse animations, node status colors)
│   ├── package.json                       ← MODIFIED (add @xyflow/react, @tanstack/react-query, zustand, @dagrejs/dagre)
│   └── ...
│
├── docker/
│   ├── docker-compose.yml                 ← MODIFIED (add timescaledb service)
│   ├── api.Dockerfile
│   └── web.Dockerfile
│
├── docs/
│   ├── architecture.md
│   ├── data-models.md                     ← NEW
│   └── agent-api.md                       ← NEW (NanoClaw endpoint contract)
│
├── scripts/
│   ├── dev.sh
│   └── seed.sh                            ← NEW (calls POST /dev/seed to run synthetic generator)
│
├── plan.md                                (this file)
└── README.md
```

---

## 4. Core Data Models

### 4.1 Structural Tables (standard Postgres)

**`pipelines`** — Top-level unit: one DAG, one source.
```
id              UUID PK
name            VARCHAR(255)
slug            VARCHAR(255) UNIQUE        -- URL-safe identifier (e.g. "jaffle-shop")
description     TEXT
source_type     VARCHAR(50)                -- 'dbt' | 'webhook' | 'synthetic'
source_metadata JSONB                      -- source-specific config
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**`nodes`** — A single transformation step within a pipeline.
```
id              UUID PK
pipeline_id     UUID FK → pipelines.id
external_id     VARCHAR(255)               -- node name in source system (e.g. dbt model name)
name            VARCHAR(255)
node_type       VARCHAR(50)                -- 'model' | 'source' | 'seed' | 'test' | 'task'
metadata        JSONB                      -- sql_path, materialization, tags, description
position_x      FLOAT                      -- Dagre-computed layout, persisted
position_y      FLOAT
UNIQUE(pipeline_id, external_id)
```

**`edges`** — A directed dependency between two nodes.
```
id              UUID PK
pipeline_id     UUID FK → pipelines.id
source_node_id  UUID FK → nodes.id
target_node_id  UUID FK → nodes.id
UNIQUE(pipeline_id, source_node_id, target_node_id)
```

---

### 4.2 Time-Series Tables (TimescaleDB hypertables)

**`pipeline_runs`** — One record per pipeline execution. Partitioned by `started_at`.
```
id              UUID
pipeline_id     UUID FK → pipelines.id
started_at      TIMESTAMPTZ NOT NULL       -- partition key
completed_at    TIMESTAMPTZ
status          VARCHAR(50)                -- 'running' | 'success' | 'failed' | 'partial'
triggered_by    VARCHAR(100)               -- 'schedule' | 'manual' | 'api' | 'synthetic'
metadata        JSONB
PRIMARY KEY (id, started_at)
```

**`node_runs`** — One record per node execution within a pipeline run. Partitioned by `started_at`.
```
id              UUID
pipeline_run_id UUID                       -- logical FK to pipeline_runs (not enforced at DB layer)
node_id         UUID FK → nodes.id
started_at      TIMESTAMPTZ NOT NULL       -- partition key
completed_at    TIMESTAMPTZ
status          VARCHAR(50)                -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'
duration_ms     INTEGER
rows_processed  INTEGER
error_message   TEXT
PRIMARY KEY (id, started_at)
```

> **Note**: `pipeline_run_id` is a logical reference only. TimescaleDB hypertables cannot be the target of FK constraints from other tables. Referential integrity is enforced at the application layer in `services/`.

**`metrics`** — Arbitrary time-series measurements per node. Partitioned by `time`.
```
time            TIMESTAMPTZ NOT NULL       -- partition key
node_id         UUID FK → nodes.id
metric_name     VARCHAR(100)               -- 'row_count' | 'duration_ms' | 'failure_rate'
value           DOUBLE PRECISION
PRIMARY KEY (time, node_id, metric_name)
```

---

### 4.3 Intelligence Tables

**`anomalies`** — Detected deviations from statistical baselines.
```
id              UUID PK
node_id         UUID FK → nodes.id
pipeline_run_id UUID                       -- which run triggered this anomaly
detected_at     TIMESTAMPTZ
metric_name     VARCHAR(100)               -- which metric was anomalous
observed_value  DOUBLE PRECISION
expected_value  DOUBLE PRECISION           -- rolling average baseline
z_score         DOUBLE PRECISION           -- standard deviations from mean
severity        VARCHAR(20)                -- 'low' | 'medium' | 'high' | 'critical'
description     TEXT                       -- plain-English: "Row count dropped 73% vs. 7-day avg"
resolved_at     TIMESTAMPTZ                -- NULL = unresolved
metadata        JSONB
```

---

### 4.4 Derived: Node State

Node state is **not stored** — computed at query time in `services/node_state.py`, included in every graph response and WebSocket push.

| State | Derivation logic |
|---|---|
| `running` | A `node_run` for this node has `status = 'running'` |
| `failed` | Most recent `node_run` has `status = 'failed'` |
| `drifting` | Unresolved anomaly with `severity IN ('low', 'medium')` |
| `stale` | Last successful run > 2× expected cadence ago |
| `healthy` | Most recent run succeeded, no unresolved anomalies |

---

### 4.5 WebSocket Message Contract

The WS endpoint (`ws://host/ws/pipelines/{id}/graph`) pushes a `graph_update` message whenever node state changes:

```json
{
  "type": "graph_update",
  "pipeline_id": "uuid",
  "timestamp": "2026-03-16T14:32:00Z",
  "nodes": [
    {
      "id": "uuid",
      "state": "failed",
      "last_run_at": "2026-03-16T14:31:55Z",
      "last_run_status": "failed",
      "anomaly_count": 2
    }
  ]
}
```

The initial connection response sends `"type": "graph_snapshot"` with full node + edge data. Subsequent pushes send `"type": "graph_update"` with only the changed node states (delta, not full snapshot).

---

### 4.6 NanoClaw Agent API Contract

`GET /agent/state` — structured snapshot for agent reasoning. Requires `X-Agent-Key` header.
```json
{
  "pipelines": [...],
  "anomalies": [...],           // unresolved, last 24h
  "recent_failures": [...],     // node runs with status=failed, last 6h
  "system_health": {
    "healthy_pct": 0.87,
    "drifting_count": 3,
    "failed_count": 1
  }
}
```

`GET /agent/pipeline/{id}/runs?limit=20` — run history with node-level status breakdown.

`GET /agent/node/{id}/history?metric=row_count&window=7d` — time-series for a specific metric.

---

## 5. Build Order

### Phase 1: Foundation — database + synthetic data
**Why first**: Everything else is blocked until there is data. Getting the schema right now prevents painful migrations once frontend and backend are coupled.

1. Update `docker-compose.yml`: add `timescaledb` service (`timescale/timescaledb-ha:pg17`), remove or replace any plain Postgres service
2. Add dependencies to `api/pyproject.toml`: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `apscheduler`
3. Implement `config.py` (pydantic-settings: `DATABASE_URL`, `AGENT_API_KEY`, `ENV`)
4. Implement `database.py` (async engine, session factory, `get_session` dependency)
5. Define all SQLAlchemy ORM models (`models/pipeline.py`, `models/run.py`, `models/metric.py`)
6. Initialize Alembic; write initial migration (tables + `SELECT create_hypertable(...)` for the three time-series tables)
7. Build synthetic data generator (`services/synthetic/`):
   - `dag_builder.py` — three named pipelines with fixed topologies
   - `run_simulator.py` — 90 days of run history, realistic failure patterns
   - `metric_simulator.py` — volume + duration time-series with baked-in anomalies
   - `generator.py` — orchestrates the above, idempotent (clears existing synthetic data on re-seed)
8. Expose dev-only `POST /dev/seed` endpoint

**Exit criteria**: `POST /dev/seed` populates the DB. Direct DB query shows three pipelines, nodes, 90 days of runs and metrics, and pre-baked anomalies.

---

### Phase 2: Core API read path
**Why second**: Frontend is blocked until these endpoints exist. Build reads before writes — reads unblock the graph; writes come with ingestion (Phase 5).

1. Implement Pydantic schemas for all response shapes (`schemas/`)
2. Implement `services/node_state.py` — the state derivation logic used by all graph responses
3. `GET /pipelines` — list all pipelines with summary stats
4. `GET /pipelines/{id}/graph` — full graph snapshot: nodes (with computed state) + edges
5. `GET /pipelines/{id}/runs?limit=50` — paginated run history
6. `GET /nodes/{id}/metrics?metric=row_count&window=7d` — metric time-series
7. `GET /anomalies` and `GET /pipelines/{id}/anomalies` — anomaly list with filters

**Exit criteria**: All endpoints return well-shaped JSON against seeded data. Verified via `/docs` (FastAPI auto-docs) or curl.

---

### Phase 3: WebSocket live graph
**Why third**: The graph page depends on this. Build WS before the frontend so the connection is ready when the React components are written.

1. Implement `services/ws_manager.py` — `ConnectionManager` class that tracks active WS connections per pipeline ID and exposes a `broadcast(pipeline_id, message)` method
2. Implement `routers/ws.py` — `WS /ws/pipelines/{id}/graph`:
   - On connect: send `graph_snapshot` (full node + edge data with computed states)
   - On disconnect: remove from manager
   - Integrates with `ConnectionManager`
3. Hook broadcasts into the synthetic generator's run simulator — when a simulated node run completes, broadcast a `graph_update` to subscribers
4. Register WS router in `main.py`

**Exit criteria**: Can connect to `ws://localhost:8000/ws/pipelines/{id}/graph` with a WS client, receive a snapshot immediately, and receive updates as the simulator runs.

---

### Phase 4: Flow graph UI
**Why fourth**: Visual core of the product. Build now while the data model is fresh.

1. Install frontend dependencies: `bun add @xyflow/react @tanstack/react-query zustand @dagrejs/dagre`
2. Set up `QueryClientProvider` in `App.tsx`; add `/graph` route
3. Create `lib/api.ts` (typed fetch client, `VITE_API_URL` base) and `types/pipeline.ts`
4. Build `hooks/usePipelineSocket.ts` — manages the WS lifecycle (connect on mount, reconnect on drop, expose `nodes` state and `connectionStatus`)
5. Build `store/graphStore.ts` — Zustand store: `selectedNodeId`, `isPanelOpen`, `connectionStatus`
6. Build `components/graph/PipelineGraph.tsx` — React Flow canvas, applies Dagre layout on first load, receives live node state from `usePipelineSocket`
7. Build `components/graph/nodes/PipelineNode.tsx` — custom node: name, type badge, status color ring, pulse CSS animation keyed to state
8. Build `components/graph/edges/DataFlowEdge.tsx` — animated directional edge
9. Add `styles/graph.css` — `@keyframes pulse-*` for each node state, node status color tokens
10. Build `pages/Graph.tsx` — pipeline selector + `PipelineGraph`
11. Build `components/panels/NodeDetailPanel.tsx` — slide-in on node click: last 10 runs, metric sparklines, active anomalies

**Exit criteria**: `/graph` renders a live DAG. Node colors change as the simulator runs. Clicking a node opens the detail panel.

---

### Phase 5: Anomaly detection
**Why fifth**: Needs populated metrics (Phase 1) and the read API (Phase 2). Frontend surface is small — just wiring data into existing components.

1. Implement `services/anomaly_detector.py`:
   - Rolling 14-day window: compute mean + std per node per metric
   - Flag if `|z-score| > 2.5`; severity: `low` (2.5–3.0), `medium` (3.0–4.0), `high` (4.0–5.0), `critical` (>5.0)
   - Separate detector runs for `row_count`, `duration_ms`, `failure_rate`
   - Generate plain-English description strings
   - Broadcast `anomaly_detected` WS message to affected pipeline subscribers after writing to DB
2. Schedule via APScheduler in `main.py` lifespan: run detector every 5 minutes
3. Build `components/panels/AnomalyFeed.tsx` — paginated list of recent anomalies (React Query, auto-refresh)
4. Wire `AnomalyFeed` into `pages/Insights.tsx`
5. Add anomaly indicator dot to `PipelineNode` when `anomaly_count > 0`

**Exit criteria**: Anomaly feed on `/insights` shows the baked-in anomalies from synthetic data. Affected nodes show an indicator in the graph.

---

### Phase 6: dbt ingestion
**Why sixth**: Completes the real-world ingestion story. Synthetic data handles all development and demo needs; this adds production realism.

1. Implement `services/dbt_parser.py` — parse dbt `manifest.json` into pipeline/node/edge records (models, sources, seeds, tests; dependencies from `depends_on.nodes`)
2. `POST /ingest/dbt` — accepts multipart `manifest.json` upload, upserts pipeline structure, returns created pipeline ID
3. `POST /ingest/webhook` — generic receiver: accepts `{ pipeline_id, node_id, status, rows_processed, duration_ms, timestamp }` to record a node run
4. Test `dbt_parser` against Jaffle Shop `manifest.json`

**Exit criteria**: Uploading Jaffle Shop's manifest creates a correctly structured pipeline graph.

---

### Phase 7: NanoClaw integration endpoint
**Why last**: Aggregates everything above. Trivial to implement once data is populated and queries are proven.

1. Implement `routers/agent.py` — the three endpoints from Section 4.6
2. Add `X-Agent-Key` dependency: FastAPI `Security` dependency that reads header and validates against `settings.AGENT_API_KEY`; returns `403` if missing or wrong
3. Write `docs/agent-api.md` — full endpoint contract with example request/response payloads

**Exit criteria**: Calling `GET /agent/state` with a valid API key returns a meaningful health snapshot. Calling without a key returns `403`.

---

## 6. The Single Most Important Thing

**Keep `node_runs` and `metrics` strictly separate — they are not the same concept.**

- **`node_runs`**: Event records. "This node ran at 14:32, processed 18,420 rows, took 4.2 seconds, succeeded." One row per execution. Sparse. Written once.
- **`metrics`**: Time-series measurements. "At 14:32, node X had `row_count=18420`, `duration_ms=4200`, `failure_rate=0.0`." Can come from run completion *or* from external sources (source system row counts, data quality scores). Dense over time.

The relationship: a node run completion **writes metric rows** as a side effect. But metrics are a separate, first-class table that can receive data from any source.

Why this separation matters:
1. The anomaly detector reads only `metrics` — clean, typed, queryable by time window
2. Frontend sparklines need uniform time-series — not joins across event records
3. Future metric sources (schema drift detectors, row-level quality checks) slot into `metrics` with zero impact on the run model

If these are conflated into one table, the intelligence layer breaks the moment a second metric source is added.

---

*Plan written: 2026-03-16. Decisions finalized and plan approved.*
