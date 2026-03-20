from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class EdgeResponse(BaseModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID


class NodeResponse(BaseModel):
    id: uuid.UUID
    external_id: str
    name: str
    node_type: str
    state: str  # 'healthy' | 'failed' | 'running' | 'drifting' | 'stale'
    position_x: float | None
    position_y: float | None
    last_run_at: datetime | None
    last_run_status: str | None
    anomaly_count: int


class GraphResponse(BaseModel):
    pipeline_id: uuid.UUID
    pipeline_name: str
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]


class PipelineSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    source_type: str
    node_count: int
    healthy_count: int
    failed_count: int
    drifting_count: int
    stale_count: int
    running_count: int
    created_at: datetime


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineSummary]
