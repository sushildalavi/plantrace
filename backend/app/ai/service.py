from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextvars import ContextVar
from typing import TypedDict

from fastapi import HTTPException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.evidence import EvidenceBundle, build_evidence_bundle, bundle_from_payload
from app.ai.heuristics import build_heuristic_report
from app.ai.providers import (
    AIProvider,
    build_gemini_provider,
    build_ollama_candidates,
    build_openai_provider,
)
from app.config import settings
from app.schemas import (
    QueryInvestigationOut,
    QueryInvestigationRequest,
    QueryInvestigationResponse,
)

log = logging.getLogger(__name__)
_ACTIVE_BUNDLE_PAYLOAD: ContextVar[dict[str, object] | None] = ContextVar(
    "active_bundle_payload", default=None
)


class InvestigationState(TypedDict, total=False):
    db: Session
    request: QueryInvestigationRequest
    bundle_payload: dict[str, object]
    signal_summary: str
    report: QueryInvestigationOut
    response: QueryInvestigationResponse
    provider_name: str
    model_name: str | None
    source: str
    grounded: bool
    insufficient_reason: str | None
    latency_ms: float


def _contains_banned_phrase(*parts: str) -> bool:
    banned = (
        "production cluster",
        "live cluster",
        "azure sql",
        "real customer",
        "real tenant",
        "customer tenant placement",
        "cluster controller",
    )
    text = " ".join(part for part in parts if part).lower()
    return any(term in text for term in banned)


def _summarize_signals(bundle: EvidenceBundle) -> str:
    payload = bundle.compact_payload()
    pieces: list[str] = []

    trend = payload.get("metric_trend")
    if trend:
        pieces.append(
            f"latency trend {trend['first_mean_exec_time_ms']:.2f}ms -> "
            f"{trend['latest_mean_exec_time_ms']:.2f}ms ({trend['mean_exec_time_ratio']:.2f}x)"
        )

    latest_plan = payload.get("latest_plan") or {}
    if latest_plan:
        pieces.append(
            "latest plan="
            + (
                "seq-scan"
                if latest_plan.get("uses_seq_scan")
                else "index-assisted"
                if latest_plan.get("uses_index_scan")
                else "unknown"
            )
        )
        if latest_plan.get("estimated_rows") and latest_plan.get("actual_rows"):
            est = max(float(latest_plan["estimated_rows"]), 1.0)
            pieces.append(
                f"row-estimate-ratio={float(latest_plan['actual_rows']) / est:.2f}x"
            )

    if bundle.diagnostics:
        pieces.append(
            "diagnostics="
            + ", ".join(f"{d.diagnostic_type}:{d.severity}" for d in bundle.diagnostics[:4])
        )

    if bundle.regressions:
        pieces.append(
            "regressions="
            + ", ".join(f"{r.regression_type}:{r.severity}" for r in bundle.regressions[:4])
        )

    if payload.get("plan_diff_summary"):
        diff = payload["plan_diff_summary"]
        pieces.append(f"plan-diff={diff['plan_delta']}")

    if bundle.placement_context is not None:
        pieces.append("placement-context=synthetic only")

    if not pieces:
        return "Evidence is thin: only fingerprint metadata is available."
    return "; ".join(pieces)


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "\n".join(
                    [
                        "You are PlanTrace's Query Regression Investigator.",
                        "Produce a structured, evidence-grounded SQL copilot report from telemetry, EXPLAIN, and diagnostics.",
                        "Do not invent evidence or claim production/live-cluster control.",
                        "Use only the provided signals and keep placement wording honest.",
                        "If the evidence is thin, set insufficient_evidence true.",
                        "Return rewrite and index guidance only when the bundle supports it.",
                    ]
                ),
            ),
            (
                "human",
                "\n".join(
                    [
                        "Evidence bundle:",
                        "{evidence_json}",
                        "",
                        "Signal summary:",
                        "{signal_summary}",
                        "",
                        "Return JSON only in the requested schema.",
                        "{format_instructions}",
                    ]
                ),
            ),
        ]
    )


def _bundle_from_state(state: InvestigationState) -> EvidenceBundle:
    payload = state.get("bundle_payload")
    if isinstance(payload, dict):
        return bundle_from_payload(payload)

    payload = _ACTIVE_BUNDLE_PAYLOAD.get()
    if isinstance(payload, dict):
        return bundle_from_payload(payload)

    raise HTTPException(status_code=400, detail="query evidence bundle is missing")

class QueryRegressionInvestigator:
    providers: list[AIProvider]
    timeout_seconds: int

    def __init__(
        self,
        providers: list[AIProvider] | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.providers = providers if providers is not None else self._default_providers()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.AI_TIMEOUT_SECONDS
        self._workflow = self._build_workflow()

    @staticmethod
    def _default_providers() -> list[AIProvider]:
        provider = settings.AI_PROVIDER.lower().strip()
        providers: list[AIProvider] = []
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
        if provider in {"auto", "ollama"} or settings.OLLAMA_BASE_URL:
            if provider in {"auto", "ollama"}:
                providers.extend(
                    build_ollama_candidates(
                        model_name=settings.AI_MODEL,
                        fallback_model=settings.AI_FALLBACK_MODEL,
                        base_url=settings.OLLAMA_BASE_URL,
                    )
                )
        return providers

    def _build_workflow(self):
        graph = StateGraph(InvestigationState)
        graph.add_node("collect_query_evidence", self._collect_query_evidence)
        graph.add_node("summarize_regression_signals", self._summarize_regression_signals)
        graph.add_node("run_llm_investigation", self._run_llm_investigation)
        graph.add_node("validate_report_schema", self._validate_report_schema)
        graph.add_node("check_evidence_grounding", self._check_evidence_grounding)
        graph.add_node("persist_or_return_report", self._persist_or_return_report)
        graph.set_entry_point("collect_query_evidence")
        graph.add_edge("collect_query_evidence", "summarize_regression_signals")
        graph.add_edge("summarize_regression_signals", "run_llm_investigation")
        graph.add_edge("run_llm_investigation", "validate_report_schema")
        graph.add_edge("validate_report_schema", "check_evidence_grounding")
        graph.add_edge("check_evidence_grounding", "persist_or_return_report")
        graph.add_edge("persist_or_return_report", END)
        return graph.compile()

    def _collect_query_evidence(self, state: InvestigationState) -> InvestigationState:
        if "bundle_payload" in state and state["bundle_payload"] is not None:
            return state

        db = state.get("db")
        request = state.get("request")
        if db is None or request is None:
            raise HTTPException(status_code=400, detail="query evidence requires a database session and request")

        bundle = build_evidence_bundle(
            db,
            query_id=request.query_id,
            fingerprint=request.fingerprint,
            regression_id=request.regression_id,
        )
        payload = bundle.compact_payload()
        state["bundle_payload"] = payload
        _ACTIVE_BUNDLE_PAYLOAD.set(payload)
        return state

    def _summarize_regression_signals(self, state: InvestigationState) -> InvestigationState:
        bundle = _bundle_from_state(state)
        state["signal_summary"] = _summarize_signals(bundle)
        return state

    def _invoke_chain(self, provider: AIProvider, bundle: EvidenceBundle, signal_summary: str) -> QueryInvestigationOut:
        parser = PydanticOutputParser(pydantic_object=QueryInvestigationOut)
        prompt = _build_prompt()
        chain = prompt | provider.runnable() | parser
        inputs = {
            "evidence_json": json.dumps(bundle.compact_payload(), indent=2, sort_keys=True),
            "signal_summary": signal_summary,
            "format_instructions": parser.get_format_instructions(),
        }
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chain.invoke, inputs)
            try:
                return future.result(timeout=self.timeout_seconds)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"AI provider {provider.name} timed out after {self.timeout_seconds}s") from exc

    def _run_llm_investigation(self, state: InvestigationState) -> InvestigationState:
        bundle = _bundle_from_state(state)
        signal_summary = state["signal_summary"]

        if not self.providers:
            report = build_heuristic_report(bundle, reason="AI_PROVIDER=disabled")
            state.update(
                report=report,
                provider_name="disabled",
                model_name=None,
                source="insufficient" if report.insufficient_evidence else "heuristic",
                grounded=True,
            )
            return state

        if bundle.is_thin:
            report = build_heuristic_report(bundle, reason="telemetry history is too thin")
            state.update(
                report=report,
                provider_name="heuristic",
                model_name=None,
                source="insufficient",
                grounded=True,
                insufficient_reason="telemetry history is too thin",
            )
            return state

        last_error: Exception | None = None
        for provider in self.providers:
            try:
                report = self._invoke_chain(provider, bundle, signal_summary)
                state.update(
                    report=report,
                    provider_name=provider.name,
                    model_name=provider.model_name,
                    source="llm",
                    grounded=False,
                )
                return state
            except Exception as exc:
                last_error = exc
                log.warning("investigation provider %s failed: %s", provider.name, exc)

        report = build_heuristic_report(
            bundle,
            reason=str(last_error) if last_error is not None else "provider unavailable",
        )
        state.update(
            report=report,
            provider_name=self.providers[0].name if self.providers else "heuristic",
            model_name=self.providers[0].model_name if self.providers else None,
            source="insufficient" if report.insufficient_evidence else "heuristic",
            grounded=True,
            insufficient_reason=str(last_error) if last_error is not None else "provider unavailable",
        )
        return state

    def _validate_report_schema(self, state: InvestigationState) -> InvestigationState:
        report = QueryInvestigationOut.model_validate(state["report"].model_dump())
        state["report"] = report
        return state

    def _check_evidence_grounding(self, state: InvestigationState) -> InvestigationState:
        bundle = _bundle_from_state(state)
        report = state["report"]
        allowed = {signal.lower() for signal in bundle.signal_inventory}

        report_text = " ".join(
            [
                report.summary,
                report.root_cause or "",
                report.why_this_changed or "",
                report.regression_timeline or "",
                report.affected_query_fingerprint_summary or "",
                report.remediation_priority,
                " ".join(report.likely_causes),
                " ".join(report.suggested_actions),
                " ".join(item.signal for item in report.evidence),
                " ".join(item.observed_value for item in report.evidence),
                " ".join(item.why_it_matters for item in report.evidence),
                " ".join(c.signal for c in report.evidence_citations),
                " ".join(c.observed_value for c in report.evidence_citations),
                report.query_rewrite_suggestion.rationale if report.query_rewrite_suggestion else "",
                report.index_recommendation.rationale if report.index_recommendation else "",
                report.explain_diff_summary.plan_delta if report.explain_diff_summary else "",
            ]
        )
        unsupported_signal = any(item.signal.lower() not in allowed for item in report.evidence)
        unsupported_citation = any(c.signal.lower() not in allowed for c in report.evidence_citations)
        banned_phrase = _contains_banned_phrase(report_text)
        too_thin = len(report.evidence) < 2 and not report.insufficient_evidence
        overconfident = report.confidence > 0.95 and bundle.evidence_count < 3

        if unsupported_signal or unsupported_citation or banned_phrase or too_thin or overconfident:
            fallback = build_heuristic_report(bundle, reason="grounding check rejected unsupported model claims")
            state.update(
                report=fallback,
                grounded=True,
                source="insufficient" if fallback.insufficient_evidence else "heuristic",
                insufficient_reason="grounding check rejected unsupported model claims",
            )
            return state

        state["grounded"] = True
        return state

    def _persist_or_return_report(self, state: InvestigationState) -> InvestigationState:
        report = state["report"]
        source = state.get("source", "heuristic")
        if report.insufficient_evidence and source == "llm":
            source = "insufficient"
        state["response"] = QueryInvestigationResponse(
            report=report,
            provider=state.get("provider_name", "disabled"),
            model_name=state.get("model_name"),
            source=source,  # type: ignore[arg-type]
            grounded=bool(state.get("grounded", False)),
            latency_ms=state.get("latency_ms", 0.0),
            insufficient_reason=state.get("insufficient_reason"),
        )
        return state

    def investigate(
        self,
        db: Session,
        request: QueryInvestigationRequest,
    ) -> QueryInvestigationResponse:
        return self.investigate_bundle(request=request, db=db)

    def investigate_bundle(
        self,
        *,
        request: QueryInvestigationRequest | None = None,
        bundle: EvidenceBundle | None = None,
        db: Session | None = None,
    ) -> QueryInvestigationResponse:
        if bundle is None and request is None:
            raise ValueError("either request or bundle is required")

        state: InvestigationState = {
            "request": request or QueryInvestigationRequest(query_id=bundle.fingerprint.id if bundle else None),
        }
        if db is not None:
            state["db"] = db
        if bundle is not None:
            payload = bundle.compact_payload()
            state["bundle_payload"] = payload
            _ACTIVE_BUNDLE_PAYLOAD.set(payload)

        t0 = time.perf_counter()
        try:
            result = self._workflow.invoke(state)
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            result["latency_ms"] = latency_ms
            if "response" in result:
                result["response"].latency_ms = latency_ms
                return result["response"]
            raise RuntimeError("investigation workflow did not produce a response")
        finally:
            _ACTIVE_BUNDLE_PAYLOAD.set(None)


def build_query_investigator_service(
    *,
    providers: list[AIProvider] | None = None,
    timeout_seconds: int | None = None,
) -> QueryRegressionInvestigator:
    return QueryRegressionInvestigator(providers=providers, timeout_seconds=timeout_seconds)
