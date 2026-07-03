"""query diagnostics and placement support

Revision ID: 0004_query_diagnostics_and_placement
Revises: 0003_reliability_idempotency_dlq
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0004_qdiag_place"
down_revision: str | None = "0003_reliability_idempotency_dlq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "plantrace"


def upgrade() -> None:
    op.create_table(
        "query_diagnostics",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fingerprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), nullable=True),
        sa.Column("diagnostic_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("evidence_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fingerprint_id"], [f"{SCHEMA}.query_fingerprints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], [f"{SCHEMA}.query_plans.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    op.create_index("ix_query_diagnostics_fp_created", "query_diagnostics", ["fingerprint_id", "created_at"], schema=SCHEMA)
    op.create_index("ix_query_diagnostics_plan_created", "query_diagnostics", ["plan_id", "created_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("query_diagnostics", schema=SCHEMA)
