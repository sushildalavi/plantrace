export const landingDemo = {
  queriesTracked: 428,
  slowQueries: 17,
  criticalRegressions: 4,
  avgLatencyMs: 83.42,
  topQuery: {
    fingerprintHash: "b8e9f1c3a0f6d7e2",
    normalizedQuery:
      "select * from orders where user_id = $1 order by created_at desc",
    latestMeanMs: 182.4,
    latestCalls: 1240,
    regressionCount: 3,
  },
  topRegression: {
    severity: "high" as const,
    regressionType: "index_scan_to_seq_scan",
    message: "latest plan flipped from index-assisted access to a sequential scan",
    confidence: 0.91,
  },
  placement: {
    overloadedBefore: 7,
    overloadedAfter: 2,
    hotspotReduction: 0.63,
    decisionP95: 8.4,
    migrationCost: 14.2,
  },
  pipeline: [
    "C++ collector",
    "Kafka",
    "PostgreSQL",
    "FastAPI",
    "React",
    "Prometheus / Grafana",
  ],
  validation: [
    { label: "Backend tests", value: "69 passed" },
    { label: "Ruff", value: "passed" },
    { label: "Frontend build", value: "passed" },
    { label: "Compose config", value: "passed" },
    { label: "Alembic", value: "validated" },
    { label: "Collector init", value: "validated" },
  ],
};
