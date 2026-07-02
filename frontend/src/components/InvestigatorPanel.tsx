import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import type { QueryInvestigationResponse } from "../types";
import { Section } from "./Section";

function riskStyle(risk: QueryInvestigationResponse["report"]["risk_level"]) {
  if (risk === "high") {
    return "bg-bad/10 text-bad ring-bad/30";
  }
  if (risk === "medium") {
    return "bg-warn/10 text-warn ring-warn/30";
  }
  return "bg-ok/10 text-ok ring-ok/30";
}

function SourceBadge({ source }: { source: QueryInvestigationResponse["source"] }) {
  const tone =
    source === "llm"
      ? "bg-ok/10 text-ok ring-ok/30"
      : source === "insufficient"
        ? "bg-bad/10 text-bad ring-bad/30"
        : "bg-warn/10 text-warn ring-warn/30";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-2xs font-mono uppercase tracking-wider ring-1 ${tone}`}>
      {source === "llm" ? <Sparkles size={10} /> : <Terminal size={10} />}
      {source}
    </span>
  );
}

export function InvestigatorPanel({ queryId }: { queryId: string }) {
  const investigation = useMutation({
    mutationFn: () => api.queryInvestigation({ query_id: queryId }),
  });

  const result = investigation.data;
  const report = result?.report;

  return (
    <Section
      icon={BrainCircuit}
      title="Query Regression Investigator"
      hint="evidence-grounded investigation workflow"
      action={
        <button
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md surface-2 hover:border-edge-bright text-xs text-secondary hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={investigation.isPending}
          onClick={() => investigation.mutate()}
        >
          {investigation.isPending ? (
            <Loader2 size={13} className="animate-spin text-accent" />
          ) : (
            <Zap size={13} className="text-accent" />
          )}
          {investigation.isPending ? "investigating" : "run investigator"}
        </button>
      }
    >
      <div className="p-5 space-y-4">
        <p className="text-sm text-secondary max-w-3xl">
          This workflow reads query telemetry, regression signals, and diagnostics,
          then returns a structured report. It does not chat and it will fall back to
          insufficient evidence when the telemetry history is too thin.
        </p>

        {investigation.error && (
          <div className="rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-sm text-bad">
            Failed to generate an investigation report.
          </div>
        )}

        {report ? (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="surface-2 p-3">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">risk</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-2xs font-mono uppercase tracking-wider ring-1 ${riskStyle(report.risk_level)}`}>
                    {report.risk_level === "high" ? <AlertTriangle size={10} /> : <CheckCircle2 size={10} />}
                    {report.risk_level}
                  </span>
                  <span className="text-xs text-muted font-mono">confidence {Math.round(report.confidence * 100)}%</span>
                </div>
              </div>
              <div className="surface-2 p-3">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">source</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <SourceBadge source={result?.source ?? "heuristic"} />
                  <span className="text-xs text-muted font-mono">
                    {result?.provider}
                    {result?.model_name ? ` · ${result.model_name}` : ""}
                  </span>
                </div>
              </div>
              <div className="surface-2 p-3">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">latency</p>
                <p className="mt-2 text-sm text-primary font-mono">
                  {result?.latency_ms?.toFixed(0) ?? "0"} ms
                </p>
              </div>
            </div>

            <div className={`rounded-xl border px-4 py-3 ${report.insufficient_evidence ? "border-warn/30 bg-warn/10" : "border-edge bg-panel-2/70"}`}>
              <p className="text-2xs uppercase tracking-widest text-muted font-mono">summary</p>
              <p className="mt-1.5 text-sm text-primary leading-relaxed">{report.summary}</p>
              {report.insufficient_evidence && (
                <p className="mt-2 text-xs text-warn font-mono uppercase tracking-widest">
                  insufficient evidence
                </p>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="surface-2 p-4">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">likely causes</p>
                <ul className="mt-3 space-y-2">
                  {report.likely_causes.length > 0 ? (
                    report.likely_causes.map((cause) => (
                      <li key={cause} className="rounded-lg border border-edge bg-ink/30 px-3 py-2 text-sm text-primary">
                        {cause}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted">No likely cause could be stated safely.</li>
                  )}
                </ul>
              </div>
              <div className="surface-2 p-4">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">suggested actions</p>
                <ul className="mt-3 space-y-2">
                  {report.suggested_actions.length > 0 ? (
                    report.suggested_actions.map((action) => (
                      <li key={action} className="rounded-lg border border-edge bg-ink/30 px-3 py-2 text-sm text-secondary">
                        {action}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-muted">No next step could be recommended with confidence.</li>
                  )}
                </ul>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">evidence</p>
                <span className="text-2xs text-muted font-mono">
                  {report.evidence.length} evidence item{report.evidence.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="mt-3 grid gap-3">
                {report.evidence.length > 0 ? (
                  report.evidence.map((item) => (
                    <article key={`${item.signal}-${item.observed_value}`} className="rounded-xl border border-edge bg-panel-2/60 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <p className="text-sm font-semibold text-primary">{item.signal}</p>
                        <span className="rounded-full border border-edge px-2 py-1 text-2xs font-mono uppercase tracking-wider text-muted">
                          telemetry
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-secondary font-mono">{item.observed_value}</p>
                      <p className="mt-2 text-sm text-muted leading-relaxed">{item.why_it_matters}</p>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-muted">No evidence items were emitted for this run.</p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-edge-bright bg-panel-2/40 px-4 py-5 text-sm text-muted">
            Click run investigator to generate a report for this fingerprint.
          </div>
        )}
      </div>
    </Section>
  );
}
