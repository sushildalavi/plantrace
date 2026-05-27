"""v2 streaming/collector status additions

Revision ID: 0002_v2_streaming
Revises: 0001_initial
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002_v2_streaming"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "querylens"


def upgrade() -> None:
    op.drop_constraint("ck_regression_severity", "query_regressions", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        "ck_regression_severity",
        "query_regressions",
        "severity IN ('critical','high','medium','low')",
        schema=SCHEMA,
    )

    op.create_table(
        "collector_status",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("service_id", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("database_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="ok"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_collector_status_service_id", "collector_status", ["service_id"], schema=SCHEMA)
    op.create_index("ix_collector_status_last_seen_at", "collector_status", ["last_seen_at"], schema=SCHEMA)
    op.create_index(
        "ix_collector_status_service_seen",
        "collector_status",
        ["service_id", "last_seen_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("collector_status", schema=SCHEMA)
    op.drop_constraint("ck_regression_severity", "query_regressions", schema=SCHEMA, type_="check")
    op.create_check_constraint(
        "ck_regression_severity",
        "query_regressions",
        "severity IN ('high','medium','low')",
        schema=SCHEMA,
    )
