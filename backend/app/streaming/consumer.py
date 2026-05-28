from __future__ import annotations

import asyncio
import json
import logging
import random
from contextlib import suppress
from datetime import UTC, datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from google.protobuf.json_format import MessageToDict

from app.config import settings
from app.database import SessionLocal
from app.models import DlqEvent
from app.observability.metrics import (
    dlq_events_total,
    ingest_retries_total,
    kafka_consumer_lag,
    telemetry_events_consumed_total,
    telemetry_persist_failures_total,
)
from app.proto.collector.proto import telemetry_pb2
from app.streaming.ingest import event_id_for, ingest_heartbeat_event, ingest_query_event

log = logging.getLogger(__name__)


class TelemetryConsumer:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if not settings.KAFKA_ENABLED:
            log.info("kafka consumer disabled")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    def _retry_backoffs(self) -> list[float]:
        raw = [x.strip() for x in settings.KAFKA_RETRY_BACKOFFS_MS.split(",") if x.strip()]
        vals = [max(0, int(x)) / 1000.0 for x in raw]
        return vals if vals else [0.1, 0.5, 2.0]

    async def _publish_dlq(self, producer: AIOKafkaProducer, payload: dict) -> None:
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_TELEMETRY_DLQ,
            json.dumps(payload).encode("utf-8"),
            key=str(payload.get("event_id", "unknown")).encode("utf-8"),
        )
        dlq_events_total.inc()

    async def _process_with_retry(
        self,
        topic: str,
        raw_value: bytes,
        producer: AIOKafkaProducer,
        consumer_id: str,
    ) -> bool:
        max_retries = max(0, settings.KAFKA_CONSUMER_MAX_RETRIES)
        backoffs = self._retry_backoffs()
        last_exc: Exception | None = None
        event_id = None

        for attempt in range(max_retries + 1):
            session = SessionLocal()
            try:
                if topic == settings.KAFKA_TOPIC_QUERY_TELEMETRY:
                    msg = telemetry_pb2.QueryTelemetryEvent()
                    msg.ParseFromString(raw_value)
                    event = MessageToDict(msg, preserving_proto_field_name=True)
                    event_id = event_id_for(event)
                    ingest_query_event(session, event)
                elif topic == settings.KAFKA_TOPIC_COLLECTOR_HEARTBEAT:
                    msg = telemetry_pb2.CollectorHeartbeatEvent()
                    msg.ParseFromString(raw_value)
                    event = MessageToDict(msg, preserving_proto_field_name=True)
                    event_id = f"heartbeat:{event.get('service_id','unknown')}:{event.get('captured_at','')}"
                    ingest_heartbeat_event(session, event)
                else:
                    raise ValueError(f"unsupported topic: {topic}")

                session.commit()
                telemetry_events_consumed_total.inc()
                return True
            except Exception as exc:
                session.rollback()
                telemetry_persist_failures_total.inc()
                last_exc = exc
                if attempt < max_retries:
                    ingest_retries_total.inc()
                    backoff = backoffs[min(attempt, len(backoffs) - 1)]
                    backoff += random.uniform(0, 0.05)
                    await asyncio.sleep(backoff)
                else:
                    dlq_payload = {
                        "event_id": event_id,
                        "topic": topic,
                        "failure_reason": str(exc),
                        "exception_type": type(exc).__name__,
                        "retry_count": attempt,
                        "failed_at": datetime.now(UTC).isoformat(),
                        "consumer_id": consumer_id,
                        "payload_b64": raw_value.hex(),
                    }
                    await self._publish_dlq(producer, dlq_payload)
                    # persist local DLQ record for observability
                    with SessionLocal() as dlq_sess:
                        dlq_sess.add(
                            DlqEvent(
                                topic=topic,
                                event_id=event_id,
                                failure_reason=str(exc),
                                exception_type=type(exc).__name__,
                                retry_count=attempt,
                                consumer_id=consumer_id,
                                payload_json=dlq_payload,
                            )
                        )
                        dlq_sess.commit()
            finally:
                session.close()

        if last_exc:
            log.error("exhausted retries for topic=%s error=%s", topic, last_exc)
        return False

    async def _run(self) -> None:
        consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_QUERY_TELEMETRY,
            settings.KAFKA_TOPIC_COLLECTOR_HEARTBEAT,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_GROUP_ID,
            enable_auto_commit=True,
            auto_offset_reset="latest",
            value_deserializer=lambda x: x,
        )
        producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)

        await consumer.start()
        await producer.start()
        consumer_id = f"{settings.KAFKA_GROUP_ID}:{id(self)}"
        log.info("kafka consumer started")
        try:
            while not self._stop.is_set():
                result = await consumer.getmany(timeout_ms=1000, max_records=200)
                for tp, records in result.items():
                    try:
                        end_offsets = await consumer.end_offsets([tp])
                        position = await consumer.position(tp)
                        lag = max(end_offsets.get(tp, position) - position, 0)
                        kafka_consumer_lag.labels(topic=tp.topic).set(lag)
                    except Exception:
                        pass

                    for record in records:
                        await self._process_with_retry(tp.topic, record.value, producer, consumer_id)
        finally:
            await consumer.stop()
            await producer.stop()
            log.info("kafka consumer stopped")
