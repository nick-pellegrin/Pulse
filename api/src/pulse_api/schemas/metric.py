from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MetricPoint(BaseModel):
    time: datetime
    value: float


class MetricSeriesResponse(BaseModel):
    node_id: uuid.UUID
    metric_name: str
    window: str
    points: list[MetricPoint]
