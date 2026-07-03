"""initial plantrace schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-04 10:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "plantrace"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "query_fingerprints",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_hash", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fingerprint_hash", name="uq_query_fingerprints_hash"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_fingerprints_fingerprint_hash",
        "query_fingerprints",
        ["fingerprint_hash"],
        schema=SCHEMA,
    )

    op.create_table(
        "query_metrics",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("calls", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_exec_time_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mean_exec_time_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rows_returned", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shared_blks_hit", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shared_blks_read", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("temp_blks_written", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["fingerprint_id"],
            [f"{SCHEMA}.query_fingerprints.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_metrics_captured_at", "query_metrics", ["captured_at"], schema=SCHEMA
    )
    op.create_index(
        "ix_query_metrics_fp_captured",
        "query_metrics",
        ["fingerprint_id", "captured_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "query_plans",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_json", JSONB(), nullable=False),
        sa.Column("planning_time_ms", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        sa.Column("top_node_type", sa.Text(), nullable=True),
        sa.Column("uses_seq_scan", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("uses_index_scan", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("estimated_total_cost", sa.Float(), nullable=True),
        sa.Column("actual_rows", sa.BigInteger(), nullable=True),
        sa.Column("estimated_rows", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["fingerprint_id"],
            [f"{SCHEMA}.query_fingerprints.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_plans_captured_at", "query_plans", ["captured_at"], schema=SCHEMA
    )
    op.create_index(
        "ix_query_plans_fp_captured",
        "query_plans",
        ["fingerprint_id", "captured_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "query_regressions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("regression_type", sa.Text(), nullable=False),
        sa.Column("old_metric_json", JSONB(), nullable=True),
        sa.Column("new_metric_json", JSONB(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("severity IN ('high','medium','low')", name="ck_regression_severity"),
        sa.ForeignKeyConstraint(
            ["fingerprint_id"],
            [f"{SCHEMA}.query_fingerprints.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_regressions_created_at", "query_regressions", ["created_at"], schema=SCHEMA
    )
    op.create_index(
        "ix_query_regressions_severity_created",
        "query_regressions",
        ["severity", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_regressions_fp_created",
        "query_regressions",
        ["fingerprint_id", "created_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "query_reports",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["fingerprint_id"],
            [f"{SCHEMA}.query_fingerprints.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_reports_created_at", "query_reports", ["created_at"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_table("query_reports", schema=SCHEMA)
    op.drop_table("query_regressions", schema=SCHEMA)
    op.drop_table("query_plans", schema=SCHEMA)
    op.drop_table("query_metrics", schema=SCHEMA)
    op.drop_table("query_fingerprints", schema=SCHEMA)
