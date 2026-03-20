"""WebSocket endpoint: ws://host/ws/pipelines/{id}/graph

On connect:
  1. Accept the connection and register with ConnectionManager.
  2. Query the pipeline, nodes, edges, and computed node states.
  3. Send a graph_snapshot message with full node + edge data.
  4. Keep the connection alive until the client disconnects.

While connected:
  - The live simulator broadcasts graph_update deltas whenever a simulated
    node run completes (see services/live_simulator.py).
  - The client may send any text (e.g. a ping); it is silently ignored.

On disconnect:
  - Remove the connection from ConnectionManager.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from pulse_api.database import AsyncSessionLocal
from pulse_api.models.pipeline import Edge, Node, Pipeline
from pulse_api.services.node_state import compute_node_states
from pulse_api.services.ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipelines/{pipeline_id}/graph")
async def ws_pipeline_graph(ws: WebSocket, pipeline_id: uuid.UUID) -> None:
    await manager.connect(pipeline_id, ws)
    try:
        async with AsyncSessionLocal() as session:
            pipeline = await session.get(Pipeline, pipeline_id)
            if pipeline is None:
                await ws.send_json({"type": "error", "detail": "Pipeline not found"})
                await ws.close(code=4004)
                return

            nodes = (
                await session.execute(
                    select(Node).where(Node.pipeline_id == pipeline_id)
                )
            ).scalars().all()
            edges = (
                await session.execute(
                    select(Edge).where(Edge.pipeline_id == pipeline_id)
                )
            ).scalars().all()

            node_ids = [n.id for n in nodes]
            states = await compute_node_states(session, node_ids, pipeline_id)

        snapshot = {
            "type": "graph_snapshot",
            "pipeline_id": str(pipeline_id),
            "pipeline_name": pipeline.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nodes": [
                {
                    "id": str(n.id),
                    "external_id": n.external_id,
                    "name": n.name,
                    "node_type": n.node_type,
                    "state": states[n.id].state,
                    "position_x": n.position_x,
                    "position_y": n.position_y,
                    "last_run_at": (
                        states[n.id].last_run_at.isoformat()
                        if states[n.id].last_run_at
                        else None
                    ),
                    "last_run_status": states[n.id].last_run_status,
                    "anomaly_count": states[n.id].anomaly_count,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": str(e.id),
                    "source_node_id": str(e.source_node_id),
                    "target_node_id": str(e.target_node_id),
                }
                for e in edges
            ],
        }
        await ws.send_json(snapshot)

        # Keep the connection alive — client may send pings, we ignore them
        while True:
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(pipeline_id, ws)
