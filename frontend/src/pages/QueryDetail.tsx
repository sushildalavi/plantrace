import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Copy,
  FileText,
  GitBranch,
  Hash,
  History,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  useGenerateReport,
  useDiagnostics,
  useLatestPlan,
  useMetrics,
  useRecommendations,
  useQuery_,
  useRegressions,
  useReport,
} from "../api/hooks";
import { LatencyChart } from "../components/LatencyChart";
import { PlanViewer } from "../components/PlanViewer";
import { InvestigatorPanel } from "../components/InvestigatorPanel";
import { RegressionBadge } from "../components/RegressionBadge";
import { RegressionTypeIcon, regressionMeta } from "../components/RegressionTypeIcon";
import { Section, Skeleton } from "../components/Section";
import { SqlCode } from "../components/SqlCode";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="inline-flex items-center gap-1.5 text-2xs text-muted hover:text-primary transition-colors px-2 py-1 rounded border border-edge hover:border-edge-bright bg-panel"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? "copied" : "copy"}
    </button>
  );
}

export function QueryDetail() {
  const { fid = "" } = useParams<{ fid: string }>();
  const { data: detail, isLoading: dLoading } = useQuery_(fid);
  const { data: metrics = [] } = useMetrics(fid);
  const { data: plan } = useLatestPlan(fid);
  const { data: diagnostics } = useDiagnostics(fid);
  const { data: recommendations } = useRecommendations(fid);
  const { data: regsPage } = useRegressions({ limit: 50 });
  const { data: existingReport } = useReport(fid);
  const generateMutation = useGenerateReport(fid);
  const [report, setReport] = useState<string | null>(null);

  const myRegs = (regsPage?.items ?? []).filter(
    (r) => r.fingerprint_id === fid
  );

  const handleReport = async () => {
    try {
      const r = await generateMutation.mutateAsync();
      setReport(r.generated_text);
    } catch {
      setReport("Failed to generate report.");
    }
  };

  if (dLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!detail)
    return (
      <div className="surface p-8 text-center">
        <p className="text-bad text-sm">Query not found.</p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 mt-3 text-2xs text-muted hover:text-primary"
        >
          <ArrowLeft size={12} /> back to overview
        </Link>
      </div>
    );

  const fp = detail.fingerprint;
  const latestMetric = detail.latest_metric;
  const recItems = recommendations?.items ?? [];
  const hasHighReg = myRegs.some((r) => r.severity === "high" || r.severity === "critical");
  const isVectorQuery = /<=>|<->|<#>/.test(fp.normalized_query);

  return (
    <div className="space-y-6">
      <div className="animate-fade-up">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-2xs text-muted hover:text-primary font-mono uppercase tracking-widest transition-colors"
        >
          <ArrowLeft size={12} /> overview
        </Link>
        <div className="mt-3 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">
              query fingerprint
            </p>
            <h1 className="mt-1 font-display text-2xl font-semibold text-primary tracking-tightest flex items-center gap-2.5">
              <Hash size={18} className="text-accent" strokeWidth={2.5} />
              <span className="font-mono">{fp.fingerprint_hash.slice(0, 16)}</span>
            </h1>
            {isVectorQuery && (
              <p className="mt-2 text-2xs font-mono uppercase tracking-wider text-accent">
                vector query detected
              </p>
            )}
            <Link
              to={`/app/queries/${fid}/diagnostics`}
              className="inline-flex items-center gap-1.5 mt-3 text-2xs font-mono uppercase tracking-widest text-muted hover:text-primary transition-colors"
            >
              diagnostics view
              <ArrowLeft size={11} className="rotate-180" />
            </Link>
          </div>
          {hasHighReg && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-bad/10 ring-1 ring-bad/30 text-bad text-xs font-medium animate-scale-in">
              <span className="relative inline-grid place-items-center w-2 h-2">
                <span className="absolute inset-0 rounded-full bg-bad animate-pulse-ring" />
                <span className="relative w-1.5 h-1.5 rounded-full bg-bad" />
              </span>
              high-severity regression detected
            </div>
          )}
        </div>
      </div>

      <div className="surface relative animate-fade-up">
        <div className="absolute top-2.5 right-2.5 z-10">
          <CopyButton text={fp.normalized_query} />
        </div>
        <div className="absolute left-0 top-0 bottom-0 w-9 border-r border-edge bg-panel-2/40 pointer-events-none" />
        <div className="absolute left-0 top-0 bottom-0 w-9 flex flex-col items-center pt-4 text-2xs text-muted font-mono select-none pointer-events-none">
          {fp.normalized_query.split("\n").map((_, i) => (
            <span key={i} className="leading-relaxed">
              {i + 1}
            </span>
          ))}
        </div>
        <div className="pl-12 pr-20 py-4 overflow-x-auto">
          <SqlCode sql={fp.normalized_query} />
        </div>
      </div>

      {latestMetric && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger-fast">
          {[
            {
              label: "Mean exec",
              val: latestMetric.mean_exec_time_ms.toFixed(2),
              suffix: "ms",
            },
            {
              label: "Total calls",
              val: latestMetric.calls.toLocaleString(),
              suffix: "",
            },
            {
              label: "Rows returned",
              val: latestMetric.rows_returned.toLocaleString(),
              suffix: "",
            },
            {
              label: "Temp blocks",
              val: latestMetric.temp_blks_written.toLocaleString(),
              suffix: "",
            },
          ].map(({ label, val, suffix }) => (
            <div key={label} className="surface px-4 py-3">
              <p className="text-2xs uppercase tracking-widest text-muted font-medium">
                {label}
              </p>
              <p className="text-xl font-semibold text-primary tracking-tight num mt-1.5">
                {val}
                {suffix && (
                  <span className="text-muted text-sm font-normal ml-1">
                    {suffix}
                  </span>
                )}
              </p>
            </div>
          ))}
        </div>
      )}

      {metrics.length > 0 && (
        <div className="grid md:grid-cols-2 gap-4">
          <Section icon={TrendingUp} title="Mean exec time" hint="ms · over time">
            <div className="px-5 py-4">
              <LatencyChart
                points={metrics}
                dataKey="mean_exec_time_ms"
                color="#f59e0b"
                unit="ms"
              />
            </div>
          </Section>
          <Section icon={History} title="Call count" hint="calls observed">
            <div className="px-5 py-4">
              <LatencyChart
                points={metrics}
                dataKey="calls"
                color="#34d399"
              />
            </div>
          </Section>
        </div>
      )}

      <Section
        icon={Sparkles}
        title="Query diagnostics"
        hint={
          diagnostics?.diagnostic_count
            ? `${diagnostics.diagnostic_count} diagnostic finding${
                diagnostics.diagnostic_count === 1 ? "" : "s"
              }`
            : "No stored diagnostic findings yet"
        }
      >
        <div className="p-5 space-y-3">
          {(diagnostics?.diagnostics ?? []).length > 0 ? (
            diagnostics!.diagnostics.map((diag) => (
              <article key={diag.id} className="rounded-xl border border-edge bg-panel-2/70 p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-primary">{diag.title}</p>
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono mt-1">
                      {diag.diagnostic_type} · {diag.severity}
                    </p>
                  </div>
                  <span className="chip chip--muted">{diag.evidence_json && Object.keys(diag.evidence_json).length} evidence fields</span>
                </div>
                <p className="text-sm text-secondary leading-relaxed">{diag.explanation}</p>
                {diag.suggested_action && (
                  <p className="text-sm text-primary leading-relaxed">{diag.suggested_action}</p>
                )}
              </article>
            ))
          ) : (
            <p className="text-sm text-muted">
              No persisted diagnostics have been stored for this fingerprint yet. Run the collector or streaming ingest after an EXPLAIN ANALYZE capture to populate this panel.
            </p>
          )}
        </div>
      </Section>

      <InvestigatorPanel queryId={fid} />

      <Section
        icon={Sparkles}
        title="Deterministic recommendations"
        hint={recItems.length > 0 ? `${recItems.length} rule-based suggestion${recItems.length === 1 ? "" : "s"}` : "No actionable recommendation matched this snapshot"}
      >
        <div className="p-5 space-y-3">
          {recItems.length > 0 ? (
            recItems.map((rec) => (
              <article key={rec.id} className="rounded-xl border border-edge bg-panel-2/70 p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-primary">{rec.title}</p>
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono mt-1">
                      {rec.severity} · confidence {rec.confidence}
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-edge px-2 py-1 text-2xs font-mono uppercase tracking-wider text-muted">
                    {rec.evidence_fields.length} evidence field{rec.evidence_fields.length === 1 ? "" : "s"}
                  </span>
                </div>
                <p className="text-sm text-secondary leading-relaxed">{rec.explanation}</p>
                <p className="text-sm text-primary leading-relaxed">{rec.suggested_action}</p>
                <div className="flex flex-wrap gap-2">
                  {rec.evidence_fields.map((field) => (
                    <span key={field} className="chip chip--muted">
                      {field}
                    </span>
                  ))}
                </div>
                {rec.safe_sql ? (
                  <div className="rounded-lg border border-edge bg-panel px-3 py-2">
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono mb-1">safe sql</p>
                    <SqlCode sql={rec.safe_sql} />
                  </div>
                ) : (
                  <p className="text-2xs text-muted font-mono">No safe SQL suggestion generated for this rule.</p>
                )}
              </article>
            ))
          ) : (
            <p className="text-sm text-muted">
              The current query snapshot did not trigger any deterministic rule. That usually means the latest plan and metrics are not showing a clear regression pattern.
            </p>
          )}
        </div>
      </Section>

      {plan && (
        <Section
          icon={GitBranch}
          title="Latest execution plan"
          hint={
            plan.execution_time_ms != null
              ? `executed in ${plan.execution_time_ms.toFixed(2)}ms${
                  plan.planning_time_ms != null
                    ? ` · planned in ${plan.planning_time_ms.toFixed(2)}ms`
                    : ""
                }`
              : "from latest EXPLAIN"
          }
        >
          <div className="p-5">
            <PlanViewer planJson={plan.plan_json} parsed={plan} />
          </div>
        </Section>
      )}

      {myRegs.length > 0 && (
        <Section icon={History} title="Regression history" hint={`${myRegs.length} detected`}>
          <ul className="divide-y divide-edge stagger-fast">
            {myRegs.map((r) => {
              const meta = regressionMeta(r.regression_type);
              return (
                <li key={r.id} className="flex items-start gap-3 px-5 py-3">
                  <RegressionBadge severity={r.severity} className="mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-primary flex items-center gap-2">
                      <RegressionTypeIcon type={r.regression_type} size={13} />
                      <span className="text-2xs font-mono text-muted uppercase tracking-wider">
                        {meta.label}
                      </span>
                    </p>
                    <p className="text-sm text-secondary mt-1.5">{r.message}</p>
                    <p className="text-2xs text-muted mt-1 font-mono">
                      {new Date(r.created_at).toLocaleString()}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      <Section
        icon={FileText}
        title="Performance report"
        hint="plain-English summary built from collected facts"
        action={
          <button
            onClick={handleReport}
            disabled={generateMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent/15 hover:bg-accent/25 text-accent ring-1 ring-accent/30 rounded text-xs font-medium transition-colors disabled:opacity-60"
          >
            <Sparkles size={12} className={generateMutation.isPending ? "animate-pulse" : ""} />
            {generateMutation.isPending
              ? "Generating…"
              : report || existingReport
              ? "Regenerate"
              : "Generate"}
          </button>
        }
      >
        <div className="p-5">
          {(report ?? existingReport?.generated_text) ? (
            <div>
              <p className="text-sm text-primary leading-relaxed whitespace-pre-wrap">
                {report ?? existingReport?.generated_text}
              </p>
              {existingReport?.model_name && !report && (
                <p className="mt-3 text-2xs text-muted font-mono">
                  generated by {existingReport.model_name}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted">
              No report yet. Click <span className="text-accent">Generate</span> to
              produce a 2–4 sentence summary from collected metrics and plan facts.
            </p>
          )}
        </div>
      </Section>
    </div>
  );
}
