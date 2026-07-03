from __future__ import annotations

import pytest

from app.config import settings
from app.proto.collector.proto import telemetry_pb2
from app.streaming import consumer as consumer_mod


class DummySession:
    def __init__(self):
        self.added = []

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def add(self, x):
        self.added.append(x)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyProducer:
    def __init__(self):
        self.sent = []

    async def send_and_wait(self, topic, value, key=None):
        self.sent.append((topic, value, key))


@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch):
    c = consumer_mod.TelemetryConsumer()
    attempts = {"n": 0}

    def fake_session_local():
        return DummySession()

    def fake_ingest(session, event):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient")
        return "inserted"

    monkeypatch.setattr(consumer_mod, "SessionLocal", fake_session_local)
    monkeypatch.setattr(consumer_mod, "ingest_query_event", fake_ingest)

    msg = telemetry_pb2.QueryTelemetryEvent(
        database_name="plantrace",
        environment="test",
        service_id="c1",
        query_fingerprint="abc",
        normalized_sql="select 1",
        captured_at="2026-05-26T00:00:00Z",
    )
    payload = msg.SerializeToString()

    ok = await c._process_with_retry(settings.KAFKA_TOPIC_QUERY_TELEMETRY, payload, DummyProducer(), "test-consumer")
    assert ok is True
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_final_failure_routes_to_dlq(monkeypatch):
    c = consumer_mod.TelemetryConsumer()

    def fake_session_local():
        return DummySession()

    def always_fail(session, event):
        raise ValueError("bad payload")

    monkeypatch.setattr(consumer_mod, "SessionLocal", fake_session_local)
    monkeypatch.setattr(consumer_mod, "ingest_query_event", always_fail)

    msg = telemetry_pb2.QueryTelemetryEvent(
        database_name="plantrace",
        environment="test",
        service_id="c1",
        query_fingerprint="abc",
        normalized_sql="select 1",
        captured_at="2026-05-26T00:00:00Z",
    )
    payload = msg.SerializeToString()
    producer = DummyProducer()

    ok = await c._process_with_retry(settings.KAFKA_TOPIC_QUERY_TELEMETRY, payload, producer, "test-consumer")
    assert ok is False
    assert len(producer.sent) == 1
    assert producer.sent[0][0] == settings.KAFKA_TOPIC_TELEMETRY_DLQ


@pytest.mark.asyncio
async def test_malformed_payload_routes_to_dlq(monkeypatch):
    c = consumer_mod.TelemetryConsumer()

    def fake_session_local():
        return DummySession()

    monkeypatch.setattr(consumer_mod, "SessionLocal", fake_session_local)

    producer = DummyProducer()
    ok = await c._process_with_retry(
        settings.KAFKA_TOPIC_QUERY_TELEMETRY,
        b"not-protobuf",
        producer,
        "test-consumer",
    )
    assert ok is False
    assert len(producer.sent) == 1
