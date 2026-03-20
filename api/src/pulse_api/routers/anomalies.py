from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.database import get_session
from pulse_api.models.metric import Anomaly
from pulse_api.models.pipeline import Node
from pulse_api.schemas.anomaly import AnomalyListResponse, AnomalyResponse

router = APIRouter(tags=["anomalies"])


def _to_response(a: Anomaly) -> AnomalyResponse:
    return AnomalyResponse(
        id=a.id,
        node_id=a.node_id,
        pipeline_run_id=a.pipeline_run_id,
        detected_at=a.detected_at,
        metric_name=a.metric_name,
        observed_value=a.observed_value,
        expected_value=a.expected_value,
        z_score=a.z_score,
        severity=a.severity,
        description=a.description,
        resolved_at=a.resolved_at,
    )


@router.get("/anomalies", response_model=AnomalyListResponse)
async def list_anomalies(
    resolved: bool | None = Query(default=None, description="Filter by resolved status"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AnomalyListResponse:
    conditions = []
    if resolved is True:
        conditions.append(Anomaly.resolved_at.is_not(None))
    elif resolved is False:
        conditions.append(Anomaly.resolved_at.is_(None))
    if severity is not None:
        conditions.append(Anomaly.severity == severity)

    base = select(Anomaly)
    count = select(func.count(Anomaly.id))
    if conditions:
        base = base.where(and_(*conditions))
        count = count.where(and_(*conditions))

    total = (await session.execute(count)).scalar_one()
    anomalies = (
        await session.execute(base.order_by(Anomaly.detected_at.desc()).limit(limit).offset(offset))
    ).scalars().all()

    return AnomalyListResponse(anomalies=[_to_response(a) for a in anomalies], total=total)


@router.get("/pipelines/{pipeline_id}/anomalies", response_model=AnomalyListResponse)
async def list_pipeline_anomalies(
    pipeline_id: uuid.UUID,
    resolved: bool | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AnomalyListResponse:
    conditions = [Node.pipeline_id == pipeline_id]
    if resolved is True:
        conditions.append(Anomaly.resolved_at.is_not(None))
    elif resolved is False:
        conditions.append(Anomaly.resolved_at.is_(None))
    if severity is not None:
        conditions.append(Anomaly.severity == severity)

    base = select(Anomaly).join(Node, Anomaly.node_id == Node.id).where(and_(*conditions))
    count = select(func.count(Anomaly.id)).join(Node, Anomaly.node_id == Node.id).where(and_(*conditions))

    total = (await session.execute(count)).scalar_one()
    anomalies = (
        await session.execute(base.order_by(Anomaly.detected_at.desc()).limit(limit).offset(offset))
    ).scalars().all()

    return AnomalyListResponse(anomalies=[_to_response(a) for a in anomalies], total=total)
