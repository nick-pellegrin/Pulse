from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PipelineRunResponse(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: str
    triggered_by: str | None


class RunListResponse(BaseModel):
    pipeline_id: uuid.UUID
    runs: list[PipelineRunResponse]
    total: int
