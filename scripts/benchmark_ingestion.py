from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from aiokafka import AIOKafkaProducer
from sqlalchemy import create_engine, text

from app.config import Settings
from app.proto.collector.proto import telemetry_pb2


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return sorted(values)[k]


async def produce_events(bootstrap_servers: str, settings: Settings, run_id: str, n: int):
    producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    await producer.start()
    try:
        started = time.perf_counter()
        for i in range(n):
            ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            fp = f"bench-{run_id}-{i}"
            evt = telemetry_pb2.QueryTelemetryEvent(
                database_name="querylens",
                environment=settings.ENVIRONMENT,
                service_id="bench-producer",
                query_fingerprint=fp,
                normalized_sql=f"select benchmark_{run_id}_{i}",
                raw_query_sample=f"select benchmark_{run_id}_{i}",
                calls=1,
                total_exec_time_ms=10.0,
                mean_exec_time_ms=10.0,
                rows=1,
                shared_blks_hit=1,
                shared_blks_read=0,
                temp_blks_read=0,
                temp_blks_written=0,
                is_vector_query=False,
                captured_at=ts,
            )
            payload = evt.SerializeToString()
            key = f"querylens:{settings.ENVIRONMENT}:{fp}".encode("utf-8")
            await producer.send_and_wait(settings.KAFKA_TOPIC_QUERY_TELEMETRY, payload, key=key)
        await producer.flush()
        finished = time.perf_counter()
    finally:
        await producer.stop()
    return started, finished


def poll_metrics(base_url: str) -> dict[str, float]:
    import urllib.request

    with urllib.request.urlopen(f"{base_url.rstrip('/')}/metrics", timeout=5) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    out: dict[str, float] = {}
    for line in body.splitlines():
        if line.startswith("querylens_kafka_consumer_lag") and not line.startswith("#"):
            try:
                out["kafka_lag"] = max(out.get("kafka_lag", 0.0), float(line.rsplit(" ", 1)[-1]))
            except Exception:
                pass
        if line.startswith("querylens_duplicate_events_total") and not line.startswith("#"):
            out["duplicates"] = float(line.rsplit(" ", 1)[-1])
        if line.startswith("querylens_dlq_events_total") and not line.startswith("#"):
            out["dlq"] = float(line.rsplit(" ", 1)[-1])
        if line.startswith("querylens_telemetry_persist_failures_total") and not line.startswith("#"):
            out["persist_failures"] = float(line.rsplit(" ", 1)[-1])
    return out


def fetch_ingest_latency_ms(db_url: str, run_id: str) -> list[float]:
    engine = create_engine(db_url, future=True)
    q = text(
        """
        SELECT EXTRACT(EPOCH FROM (m.ingested_at - m.captured_at)) * 1000.0 AS lag_ms
        FROM querylens.query_metrics m
        JOIN querylens.query_fingerprints f ON f.id = m.fingerprint_id
        WHERE f.normalized_query LIKE :prefix
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q, {"prefix": f"select benchmark_{run_id}_%"}).fetchall()
    engine.dispose()
    return [float(r.lag_ms) for r in rows if r.lag_ms is not None]


def fetch_count(db_url: str, run_id: str) -> int:
    engine = create_engine(db_url, future=True)
    q = text(
        """
        SELECT count(*)
        FROM querylens.query_metrics m
        JOIN querylens.query_fingerprints f ON f.id = m.fingerprint_id
        WHERE f.normalized_query LIKE :prefix
        """
    )
    with engine.connect() as conn:
        n = conn.execute(q, {"prefix": f"select benchmark_{run_id}_%"}).scalar_one()
    engine.dispose()
    return int(n)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--api-base", default="http://localhost:8765")
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    args = parser.parse_args()

    settings = Settings()
    db_url = settings.DATABASE_URL.replace("@db:", "@localhost:").replace(":5432/", ":5434/")
    run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    t0, t1 = await produce_events(args.bootstrap_servers, settings, run_id, args.events)
    produce_duration = t1 - t0

    lag_peak = 0.0
    recovery_start = time.perf_counter()
    lag_recovered_at = None
    while True:
        count = fetch_count(db_url, run_id)
        m = poll_metrics(args.api_base)
        lag_peak = max(lag_peak, m.get("kafka_lag", 0.0))
        if count >= args.events and m.get("kafka_lag", 0.0) <= 0.0:
            lag_recovered_at = time.perf_counter()
            break
        if time.perf_counter() - recovery_start > 300:
            break
        time.sleep(1)

    lags_ms = fetch_ingest_latency_ms(db_url, run_id)
    throughput = (args.events / produce_duration) if produce_duration > 0 else 0.0

    results = {
        "run_id": run_id,
        "events": args.events,
        "produce_duration_seconds": round(produce_duration, 3),
        "events_per_second": round(throughput, 2),
        "ingest_latency_ms_p50": round(percentile(lags_ms, 50), 2),
        "ingest_latency_ms_p95": round(percentile(lags_ms, 95), 2),
        "ingest_latency_ms_p99": round(percentile(lags_ms, 99), 2),
        "kafka_lag_peak": lag_peak,
        "kafka_lag_recovery_seconds": round((lag_recovered_at - recovery_start), 3) if lag_recovered_at else None,
        "duplicate_events_skipped": poll_metrics(args.api_base).get("duplicates", 0.0),
        "dlq_events": poll_metrics(args.api_base).get("dlq", 0.0),
        "persistence_failures": poll_metrics(args.api_base).get("persist_failures", 0.0),
        "latency_sample_count": len(lags_ms),
    }

    out_dir = Path("benchmark_results")
    out_dir.mkdir(exist_ok=True)
    jpath = out_dir / f"querylens_benchmark_{args.events}.json"
    cpath = out_dir / f"querylens_benchmark_{args.events}.csv"
    jpath.write_text(json.dumps(results, indent=2))

    with cpath.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results.keys()))
        w.writeheader()
        w.writerow(results)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
