from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.database import get_session
from pulse_api.models.pipeline import Edge, Node, Pipeline
from pulse_api.models.run import PipelineRun
from pulse_api.schemas.pipeline import (
    EdgeResponse,
    GraphResponse,
    NodeResponse,
    PipelineListResponse,
    PipelineSummary,
)
from pulse_api.schemas.run import PipelineRunResponse, RunListResponse
from pulse_api.services.node_state import compute_node_states

router = APIRouter(tags=["pipelines"])


@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(
    session: AsyncSession = Depends(get_session),
) -> PipelineListResponse:
    pipelines = (await session.execute(select(Pipeline))).scalars().all()

    summaries: list[PipelineSummary] = []
    for pipeline in pipelines:
        nodes = (
            await session.execute(select(Node).where(Node.pipeline_id == pipeline.id))
        ).scalars().all()

        node_ids = [n.id for n in nodes]
        states = await compute_node_states(session, node_ids, pipeline.id)

        counts: dict[str, int] = {s: 0 for s in ("healthy", "failed", "drifting", "stale", "running")}
        for info in states.values():
            counts[info.state] += 1

        summaries.append(
            PipelineSummary(
                id=pipeline.id,
                name=pipeline.name,
                slug=pipeline.slug,
                description=pipeline.description,
                source_type=pipeline.source_type,
                node_count=len(nodes),
                healthy_count=counts["healthy"],
                failed_count=counts["failed"],
                drifting_count=counts["drifting"],
                stale_count=counts["stale"],
                running_count=counts["running"],
                created_at=pipeline.created_at,
            )
        )

    return PipelineListResponse(pipelines=summaries)


@router.get("/pipelines/{pipeline_id}/graph", response_model=GraphResponse)
async def get_graph(
    pipeline_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> GraphResponse:
    pipeline = await session.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    nodes = (
        await session.execute(select(Node).where(Node.pipeline_id == pipeline_id))
    ).scalars().all()
    edges = (
        await session.execute(select(Edge).where(Edge.pipeline_id == pipeline_id))
    ).scalars().all()

    node_ids = [n.id for n in nodes]
    states = await compute_node_states(session, node_ids, pipeline_id)

    node_responses = [
        NodeResponse(
            id=node.id,
            external_id=node.external_id,
            name=node.name,
            node_type=node.node_type,
            state=states[node.id].state,
            position_x=node.position_x,
            position_y=node.position_y,
            last_run_at=states[node.id].last_run_at,
            last_run_status=states[node.id].last_run_status,
            anomaly_count=states[node.id].anomaly_count,
        )
        for node in nodes
    ]
    edge_responses = [
        EdgeResponse(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
        )
        for edge in edges
    ]

    return GraphResponse(
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        nodes=node_responses,
        edges=edge_responses,
    )


@router.get("/pipelines/{pipeline_id}/runs", response_model=RunListResponse)
async def get_pipeline_runs(
    pipeline_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RunListResponse:
    pipeline = await session.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    total = (
        await session.execute(
            select(func.count(PipelineRun.id)).where(PipelineRun.pipeline_id == pipeline_id)
        )
    ).scalar_one()

    runs = (
        await session.execute(
            select(PipelineRun)
            .where(PipelineRun.pipeline_id == pipeline_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    return RunListResponse(
        pipeline_id=pipeline_id,
        runs=[
            PipelineRunResponse(
                id=run.id,
                pipeline_id=run.pipeline_id,
                started_at=run.started_at,
                completed_at=run.completed_at,
                status=run.status,
                triggered_by=run.triggered_by,
            )
            for run in runs
        ],
        total=total,
    )
