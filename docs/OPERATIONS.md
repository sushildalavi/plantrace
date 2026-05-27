# Operations Guide

## Services and Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend | 3030 | http://localhost:3030 |
| Backend API | 8765 | http://localhost:8765 |
| PostgreSQL | 5434 | `psql -h localhost -p 5434 -U querylens -d querylens` |
| Kafka (Redpanda) | 9092 | internal broker |
| Redpanda Admin | 9644 | http://localhost:9644 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 (admin/admin) |

## Environment Variables

### Backend (`backend/.env` or docker-compose env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://querylens:querylens@db:5432/querylens` | SQLAlchemy connection string |
| `MIN_MEAN_MS` | `0.0` | Skip queries below this mean execution time |
| `ALLOW_EXPLAIN_ANALYZE` | `false` | Enable `EXPLAIN ANALYZE` (adds actual timing) |
| `EXPLAIN_TIMEOUT_MS` | `5000` | Per-query EXPLAIN timeout |
| `KAFKA_ENABLED` | `false` | Enable Kafka consumer on startup |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Broker address |
| `KAFKA_GROUP_ID` | `querylens-control-plane` | Consumer group |
| `KAFKA_TOPIC_QUERY_TELEMETRY` | `query-telemetry` | Telemetry events topic |
| `KAFKA_TOPIC_COLLECTOR_HEARTBEAT` | `collector-heartbeats` | Heartbeat events topic |
| `LLM_ENABLED` | `false` | Enable LLM-powered report generation |
| `OPENAI_API_KEY` | (empty) | API key for LLM reports |
| `LLM_MODEL` | `gpt-4o-mini` | Model for report generation |
| `CORS_ORIGINS` | `http://localhost:3030` | Comma-separated allowed origins |

### Collector (C++ binary, env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `COLLECTOR_DSN` | `postgresql://querylens:querylens@db:5432/querylens` | libpq connection string |
| `COLLECTOR_ENVIRONMENT` | `local` | Environment tag |
| `COLLECTOR_SERVICE_ID` | `collector-cpp` | Service identifier |
| `COLLECTOR_MIN_MEAN_MS` | `0` | Skip queries below this threshold |
| `COLLECTOR_EXPLAIN_TIMEOUT_MS` | `5000` | EXPLAIN statement timeout |
| `COLLECTOR_STDOUT_MODE` | `false` | Print to stdout instead of Kafka |

### Regression thresholds (backend env)

| Variable | Default | Description |
|----------|---------|-------------|
| `REGRESSION_LATENCY_RATIO_MEDIUM` | `2.0` | Latency spike threshold |
| `REGRESSION_LATENCY_RATIO_HIGH` | `5.0` | Severe latency spike threshold |
| `REGRESSION_ROW_ESTIMATE_RATIO` | `10.0` | Row estimate mismatch threshold |
| `REGRESSION_TEMP_BLKS_DELTA` | `1000` | Temp spill block delta |
| `REGRESSION_CALL_RATIO` | `2.0` | Call spike threshold |
| `REGRESSION_COST_RATIO` | `2.0` | Cost spike threshold |
| `REGRESSION_HNSW_SEVERITY` | `critical` | HNSW bypass severity level |

## Health and Monitoring

- **API health**: `GET /health` — returns `{"status": "ok", "db": "ok"}`
- **Prometheus metrics**: `GET /metrics` — standard Prometheus scrape endpoint
- **Collector status**: `GET /api/collector/status` — latest heartbeat info

### Key Prometheus metrics

| Metric | Type | Description |
|--------|------|-------------|
| `querylens_telemetry_events_consumed_total` | Counter | Events consumed from Kafka |
| `querylens_telemetry_persist_failures_total` | Counter | Failed persistence attempts |
| `querylens_failed_explain_captures_total` | Counter | Events missing EXPLAIN payload |
| `querylens_regression_events_total` | Counter | Regressions by severity and type |
| `querylens_kafka_consumer_lag` | Gauge | Consumer lag per topic |
| `querylens_api_request_latency_seconds` | Histogram | API request latency |
| `querylens_collector_heartbeat_age_seconds` | Gauge | Heartbeat freshness |

## Common Operations

```bash
# View logs
make logs                    # backend + collector
docker compose logs -f       # all services

# Reset demo data
make demo-reset

# Run collector manually
make collect-cpp             # C++ collector via Docker
make collect                 # Python collector (legacy v1 path)

# Run workload
make workload                # 500 iterations (default)
make workload N=2000         # custom iteration count

# Database access
docker compose exec db psql -U querylens -d querylens
```

## Debugging

- **Collector not producing**: Set `COLLECTOR_STDOUT_MODE=true` to see events on stdout
- **Kafka consumer not starting**: Check `KAFKA_ENABLED=true` in backend env
- **No regressions appearing**: Need at least 2 collector runs (baseline + comparison)
- **EXPLAIN missing from plans**: Check `ALLOW_EXPLAIN_ANALYZE` and `EXPLAIN_TIMEOUT_MS`
