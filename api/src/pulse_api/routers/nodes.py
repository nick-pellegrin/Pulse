from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.database import get_session
from pulse_api.models.metric import Metric
from pulse_api.models.pipeline import Node
from pulse_api.schemas.metric import MetricPoint, MetricSeriesResponse

router = APIRouter(tags=["nodes"])

_WINDOW_MAP: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}


@router.get("/nodes/{node_id}/metrics", response_model=MetricSeriesResponse)
async def get_node_metrics(
    node_id: uuid.UUID,
    metric: str = Query(..., description="Metric name, e.g. row_count or duration_ms"),
    window: str = Query(default="7d", description="Time window: 1d, 7d, 30d, 90d"),
    session: AsyncSession = Depends(get_session),
) -> MetricSeriesResponse:
    node = await session.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    delta = _WINDOW_MAP.get(window)
    if delta is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid window '{window}'. Use: {', '.join(_WINDOW_MAP)}",
        )

    since = datetime.now(timezone.utc) - delta
    rows = (
        await session.execute(
            select(Metric.time, Metric.value)
            .where(
                and_(
                    Metric.node_id == node_id,
                    Metric.metric_name == metric,
                    Metric.time >= since,
                )
            )
            .order_by(Metric.time.asc())
        )
    ).fetchall()

    return MetricSeriesResponse(
        node_id=node_id,
        metric_name=metric,
        window=window,
        points=[MetricPoint(time=r.time, value=r.value) for r in rows],
    )
