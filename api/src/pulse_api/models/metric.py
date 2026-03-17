from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pulse_api.database import Base


class Metric(Base):
    """Time-series measurements per node. Stored in a TimescaleDB hypertable partitioned by time.

    Separate from NodeRun — a node run completion writes metric rows, but metrics can also
    arrive from external sources (quality checks, source system counts, etc.).
    The anomaly detector reads only this table, never node_runs directly.
    """

    __tablename__ = "metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    value: Mapped[float] = mapped_column(Double, nullable=False)


class Anomaly(Base):
    """A detected deviation from a statistical baseline for a specific node metric."""

    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    # Logical FK only — pipeline_run_id not enforced at DB level
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_value: Mapped[float] = mapped_column(Double, nullable=False)
    expected_value: Mapped[float] = mapped_column(Double, nullable=False)
    z_score: Mapped[float | None] = mapped_column(Double)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
