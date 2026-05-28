"""reliability primitives: event idempotency + dlq table

Revision ID: 0003_reliability_idempotency_dlq
Revises: 0002_v2_streaming
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0003_reliability_idempotency_dlq"
down_revision: str | None = "0002_v2_streaming"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "querylens"


def upgrade() -> None:
    op.add_column("query_metrics", sa.Column("event_id", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column(
        "query_metrics",
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_query_metrics_event_id", "query_metrics", ["event_id"], unique=True, schema=SCHEMA)
    op.create_index("ix_query_metrics_ingested_at", "query_metrics", ["ingested_at"], schema=SCHEMA)

    op.create_table(
        "dlq_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("exception_type", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consumer_id", sa.Text(), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("failed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_dlq_events_event_id", "dlq_events", ["event_id"], schema=SCHEMA)
    op.create_index("ix_dlq_events_failed_at", "dlq_events", ["failed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("dlq_events", schema=SCHEMA)
    op.drop_index("ix_query_metrics_ingested_at", table_name="query_metrics", schema=SCHEMA)
    op.drop_index("ix_query_metrics_event_id", table_name="query_metrics", schema=SCHEMA)
    op.drop_column("query_metrics", "ingested_at", schema=SCHEMA)
    op.drop_column("query_metrics", "event_id", schema=SCHEMA)
