# Query Regression Investigator

PlanTrace includes an evidence-grounded AI SQL Copilot / Query Regression Investigator for query detail views and API consumers.

## What it does

- Reads query fingerprints, metric trends, regression rows, and diagnostic findings
- Produces a structured report with summary, risk level, confidence, root cause, EXPLAIN diff, likely causes, citations, rewrite guidance, index guidance, and suggested actions
- Falls back safely to `insufficient_evidence` when telemetry is thin or model output is not grounded
- Treats placement references as synthetic what-if context only
- Validates unsupported claims and rejects model output that references evidence not present in the bundle

## Default configuration

The backend does not require a model server at startup.

```bash
AI_PROVIDER=disabled
AI_TIMEOUT_SECONDS=20
```

## Optional Ollama setup

If you want a local model, run Ollama and configure:

```bash
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
AI_MODEL=qwen2.5-coder:7b
AI_FALLBACK_MODEL=llama3.1:8b
```

Recommended local models:

- `qwen2.5-coder:7b`
- `llama3.1:8b`

The investigator uses LangChain for the structured model wrapper and LangGraph for the workflow. If Ollama is unavailable, the request path falls back to a grounded heuristic report and never invents production or live-cluster claims.

Optional remote providers:

- OpenAI: set `OPENAI_API_KEY` and `AI_PROVIDER=openai` or `auto`
- Gemini: set `GEMINI_API_KEY` and `AI_PROVIDER=gemini` or `auto`

## Fake provider in CI

CI and tests use a fake provider so the workflow can be exercised without a local model server.

- `test_ai_investigation.py` covers fake-provider success, invalid JSON, timeout fallback, schema validation, grounding rejection, plan diff narration, and the API endpoint
- The fake provider returns deterministic structured output so the workflow remains reproducible

## Evaluation harness

Run the smoke harness locally:

```bash
python scripts/evaluate_query_investigator.py --provider fake
```

If Ollama is running locally, you can try:

```bash
python scripts/evaluate_query_investigator.py --provider ollama
```

The harness reports:

- schema validity rate
- evidence coverage rate
- unsupported claim rate
- recommendation relevance rate
- insufficient-evidence behavior
- average report generation latency
- number of golden regression cases tested

If Ollama is not available, the Ollama run exits with a skip message and does not fabricate results.

## API

```bash
POST /api/ai/query-investigation
{
  "query_id": "<fingerprint-id>"
}
```

`query_id`, `fingerprint`, and `regression_id` are accepted. The API returns the structured report plus metadata about the provider and grounding status.

## Limitations

- This is not a chat interface
- The investigator only reasons from stored telemetry and diagnostics
- Placement wording remains synthetic and does not imply live cluster control
