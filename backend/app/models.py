from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "querylens"


class Base(DeclarativeBase):
    pass


class QueryFingerprint(Base):
    __tablename__ = "query_fingerprints"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    fingerprint_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    metrics: Mapped[list[QueryMetric]] = relationship(back_populates="fingerprint", cascade="all, delete-orphan")
    plans: Mapped[list[QueryPlan]] = relationship(back_populates="fingerprint", cascade="all, delete-orphan")
    regressions: Mapped[list[QueryRegression]] = relationship(back_populates="fingerprint", cascade="all, delete-orphan")
    reports: Mapped[list[QueryReport]] = relationship(back_populates="fingerprint", cascade="all, delete-orphan")


class QueryMetric(Base):
    __tablename__ = "query_metrics"
    __table_args__ = (
        Index("ix_query_metrics_fp_captured", "fingerprint_id", "captured_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    event_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True, index=True)
    fingerprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.query_fingerprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    calls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_exec_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mean_exec_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rows_returned: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    shared_blks_hit: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    shared_blks_read: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    temp_blks_written: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    fingerprint: Mapped[QueryFingerprint] = relationship(back_populates="metrics")


class QueryPlan(Base):
    __tablename__ = "query_plans"
    __table_args__ = (
        Index("ix_query_plans_fp_captured", "fingerprint_id", "captured_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    fingerprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.query_fingerprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    planning_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_node_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    uses_seq_scan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uses_index_scan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_rows: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_rows: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fingerprint: Mapped[QueryFingerprint] = relationship(back_populates="plans")


class QueryRegression(Base):
    __tablename__ = "query_regressions"
    __table_args__ = (
        CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_regression_severity"),
        Index("ix_query_regressions_severity_created", "severity", "created_at"),
        Index("ix_query_regressions_fp_created", "fingerprint_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    fingerprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.query_fingerprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    regression_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_metric_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_metric_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    fingerprint: Mapped[QueryFingerprint] = relationship(back_populates="regressions")


class QueryReport(Base):
    __tablename__ = "query_reports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    fingerprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.query_fingerprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    fingerprint: Mapped[QueryFingerprint] = relationship(back_populates="reports")


class CollectorStatus(Base):
    __tablename__ = "collector_status"
    __table_args__ = (
        Index("ix_collector_status_service_seen", "service_id", "last_seen_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    service_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    environment: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    database_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class DlqEvent(Base):
    __tablename__ = "dlq_events"
    __table_args__ = (
        Index("ix_dlq_events_failed_at", "failed_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    exception_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    consumer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
