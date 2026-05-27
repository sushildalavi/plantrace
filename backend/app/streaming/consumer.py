from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiokafka import AIOKafkaConsumer
from google.protobuf.json_format import MessageToDict

from app.config import settings
from app.database import SessionLocal
from app.observability.metrics import (
    kafka_consumer_lag,
    telemetry_events_consumed_total,
    telemetry_persist_failures_total,
)
from app.proto.collector.proto import telemetry_pb2
from app.streaming.ingest import ingest_heartbeat_event, ingest_query_event

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
        await consumer.start()
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
                        session = SessionLocal()
                        try:
                            if record.topic == settings.KAFKA_TOPIC_QUERY_TELEMETRY:
                                msg = telemetry_pb2.QueryTelemetryEvent()
                                msg.ParseFromString(record.value)
                                event = MessageToDict(msg, preserving_proto_field_name=True)
                                ingest_query_event(session, event)
                            elif record.topic == settings.KAFKA_TOPIC_COLLECTOR_HEARTBEAT:
                                msg = telemetry_pb2.CollectorHeartbeatEvent()
                                msg.ParseFromString(record.value)
                                event = MessageToDict(msg, preserving_proto_field_name=True)
                                ingest_heartbeat_event(session, event)
                            session.commit()
                            telemetry_events_consumed_total.inc()
                        except Exception as exc:
                            session.rollback()
                            telemetry_persist_failures_total.inc()
                            log.exception("failed consuming telemetry message: %s", exc)
                        finally:
                            session.close()
        finally:
            await consumer.stop()
            log.info("kafka consumer stopped")
