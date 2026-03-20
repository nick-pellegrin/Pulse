from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    pipeline_run_id: uuid.UUID | None
    detected_at: datetime
    metric_name: str
    observed_value: float
    expected_value: float
    z_score: float | None
    severity: str
    description: str | None
    resolved_at: datetime | None


class AnomalyListResponse(BaseModel):
    anomalies: list[AnomalyResponse]
    total: int
