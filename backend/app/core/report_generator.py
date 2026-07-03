"""Report generator: builds deterministic findings from DB objects, then
renders them as a readable paragraph.

Two rendering paths:
1. Template (default, zero config) - deterministic string built from facts.
2. LLM (optional) - sends validated findings through the same provider
   abstraction used by the copilot. Falls back to template on any error so the
   feature always works.

The AI layer never determines regressions. It only reformats findings that the
detector already produced.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.ai.providers import build_gemini_provider, build_ollama_candidates, build_openai_provider
from app.config import settings
from app.models import QueryFingerprint, QueryMetric, QueryPlan, QueryRegression

log = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """You are a database performance assistant.
The user will give you validated findings about a Postgres query as JSON.
Write a concise 2-4 sentence summary in plain English.

Rules:
- Use ONLY the facts provided. Do not invent numbers, table names, or indexes.
- For suggestions use: "Candidate optimization: review whether ..."
- Never say "this will fix" or "create this index and the problem goes away".
- Do not mention that you are an AI or a language model.
"""

LLM_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", LLM_SYSTEM_PROMPT),
        ("human", "{findings_json}"),
    ]
)


# ---------------------------------------------------------------------------
# findings builder (pure, from ORM objects)
# ---------------------------------------------------------------------------


def build_findings(
    fp: QueryFingerprint,
    latest_metric: QueryMetric | None,
    latest_plan: QueryPlan | None,
    recent_regressions: list[QueryRegression],
) -> dict[str, Any]:
    findings: list[str] = []

    if latest_plan:
        findings.append(f"top plan node is {latest_plan.top_node_type}")
        if latest_plan.uses_seq_scan and not latest_plan.uses_index_scan:
            findings.append("plan uses sequential scan with no index scan")
        if latest_plan.uses_index_scan:
            findings.append("plan uses an index scan")
        if latest_plan.actual_rows is not None and latest_plan.estimated_rows is not None:
            ratio = latest_plan.actual_rows / max(latest_plan.estimated_rows, 1)
            if ratio > 10:
                findings.append(
                    f"actual rows ({latest_plan.actual_rows}) far exceed "
                    f"estimated rows ({latest_plan.estimated_rows}); "
                    f"statistics may be stale"
                )
        if latest_plan.estimated_total_cost is not None:
            findings.append(f"estimated plan cost is {latest_plan.estimated_total_cost:.1f}")

    if latest_metric:
        findings.append(f"mean execution time is {latest_metric.mean_exec_time_ms:.2f}ms")
        findings.append(f"total calls recorded: {latest_metric.calls}")

    for r in recent_regressions[:5]:
        findings.append(r.message)

    return {"normalized_query": fp.normalized_query, "findings": findings}


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _template(findings: dict[str, Any]) -> str:
    query = findings.get("normalized_query", "")
    items: list[str] = findings.get("findings", [])

    if not items:
        return (
            f'Query "{query[:80]}" has been profiled. '
            "No specific performance concerns were detected at this time."
        )

    intro = f'Query "{query[:80]}" was analysed.'
    bullets = "; ".join(items[:6])
    summary = f"{intro} Findings: {bullets}."

    # Append generic candidate suggestion if a seq scan is present
    has_seq = any("sequential scan" in f.lower() for f in items)
    if has_seq:
        summary += (
            " Candidate optimization: review whether an index on the filtered "
            "column(s) is appropriate for this workload."
        )
    return summary


def _provider_candidates() -> list[Any]:
    provider = settings.AI_PROVIDER.lower().strip()
    providers: list[Any] = []
    if provider in {"auto", "openai"} or settings.OPENAI_API_KEY:
        if settings.OPENAI_API_KEY:
            providers.append(
                build_openai_provider(
                    model_name=settings.LLM_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL,
                )
            )
    if provider in {"auto", "gemini"} or settings.GEMINI_API_KEY:
        if settings.GEMINI_API_KEY:
            providers.append(
                build_gemini_provider(
                    model_name=settings.GEMINI_MODEL,
                    api_key=settings.GEMINI_API_KEY,
                )
            )
    if provider in {"auto", "ollama"}:
        providers.extend(
            build_ollama_candidates(
                model_name=settings.AI_MODEL,
                fallback_model=settings.AI_FALLBACK_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )
        )
    return providers


def _as_text(output: Any) -> str:
    if isinstance(output, str):
        return output.strip()
    if hasattr(output, "content"):
        return str(output.content).strip()
    return str(output).strip()


def _llm(findings: dict[str, Any]) -> str:
    providers = _provider_candidates()
    if not providers:
        return _template(findings)

    inputs = {
        "findings_json": json.dumps(findings, indent=2, sort_keys=True),
    }
    last_error: Exception | None = None
    for provider in providers:
        chain = LLM_PROMPT | provider.runnable()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chain.invoke, inputs)
            try:
                return _as_text(future.result(timeout=15.0))
            except FuturesTimeoutError as exc:
                future.cancel()
                last_error = exc
            except Exception as exc:
                last_error = exc
                continue

    log.warning("llm call failed, falling back to template: %s", last_error)
    return _template(findings)


def render_report(findings: dict[str, Any]) -> tuple[str, str | None]:
    """Return (generated_text, model_name_or_None)."""
    if settings.LLM_ENABLED and _provider_candidates():
        text_out = _llm(findings)
        model_name = (
            settings.LLM_MODEL
            if settings.OPENAI_API_KEY
            else settings.GEMINI_MODEL
            if settings.GEMINI_API_KEY
            else settings.AI_MODEL
        )
        return text_out, model_name
    return _template(findings), None
