"""Initial schema: all tables + TimescaleDB hypertables

Revision ID: 0001
Revises:
Create Date: 2026-03-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── TimescaleDB extension ─────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ── Structural tables (standard Postgres) ─────────────────────────────────

    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )

    op.create_table(
        "nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("position_x", sa.Float()),
        sa.Column("position_y", sa.Float()),
        sa.UniqueConstraint("pipeline_id", "external_id", name="uq_nodes_pipeline_external"),
    )

    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "pipeline_id", "source_node_id", "target_node_id", name="uq_edges_pipeline_src_tgt"
        ),
    )

    # ── Time-series tables (TimescaleDB hypertables) ──────────────────────────
    # Composite PKs include the partition column (required by TimescaleDB).

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("triggered_by", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB()),
        sa.PrimaryKeyConstraint("id", "started_at"),
    )
    op.execute("SELECT create_hypertable('pipeline_runs', 'started_at')")

    op.create_table(
        "node_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # Logical FK only — hypertables cannot be the target of FK constraints
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("rows_processed", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.PrimaryKeyConstraint("id", "started_at"),
    )
    op.execute("SELECT create_hypertable('node_runs', 'started_at')")

    op.create_table(
        "metrics",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Double()),
        sa.PrimaryKeyConstraint("time", "node_id", "metric_name"),
    )
    op.execute("SELECT create_hypertable('metrics', 'time')")

    # ── Intelligence tables ───────────────────────────────────────────────────

    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Logical FK only
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("observed_value", sa.Double(), nullable=False),
        sa.Column("expected_value", sa.Double(), nullable=False),
        sa.Column("z_score", sa.Double()),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB()),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────

    op.create_index("ix_nodes_pipeline_id", "nodes", ["pipeline_id"])
    op.create_index(
        "ix_pipeline_runs_pipeline_started", "pipeline_runs", ["pipeline_id", "started_at"]
    )
    op.create_index(
        "ix_node_runs_node_started", "node_runs", ["node_id", "started_at"]
    )
    op.create_index("ix_node_runs_pipeline_run_id", "node_runs", ["pipeline_run_id"])
    op.create_index("ix_anomalies_node_id", "anomalies", ["node_id"])
    op.create_index("ix_anomalies_resolved_at", "anomalies", ["resolved_at"])


def downgrade() -> None:
    op.drop_table("anomalies")
    op.drop_table("metrics")
    op.drop_table("node_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("pipelines")
    op.execute("DROP EXTENSION IF EXISTS timescaledb")
