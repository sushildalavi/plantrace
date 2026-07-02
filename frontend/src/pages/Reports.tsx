import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Loader2,
  NotebookText,
  Play,
  Sparkles,
} from "lucide-react";
import { useGenerateReport, useQueries, useReport } from "../api/hooks";
import { Section, Skeleton } from "../components/Section";

export function Reports() {
  const { data: queriesPage, isLoading: queriesLoading } = useQueries({
    limit: 25,
    sort: "mean_latency_desc",
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("fid"));

  const queries = queriesPage?.items ?? [];
  const selectedQuery = useMemo(
    () => queries.find((q) => q.id === selectedId) ?? queries[0] ?? null,
    [queries, selectedId]
  );

  useEffect(() => {
    if (!queries.length) return;
    const hasSelected = selectedId ? queries.some((query) => query.id === selectedId) : false;
    if (!hasSelected && selectedQuery) {
      setSelectedId(selectedQuery.id);
    }
  }, [queries, selectedId, selectedQuery]);

  useEffect(() => {
    if (selectedId) {
      setSearchParams({ fid: selectedId });
    }
  }, [selectedId, setSearchParams]);

  const { data: report, isLoading: reportLoading, isError: reportError } = useReport(selectedId ?? "");
  const generateMutation = useGenerateReport(selectedId ?? "");

  const findingsCount = report?.findings.findings?.length ?? 0;
  const hasQuery = selectedQuery != null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between animate-fade-up">
        <div>
          <p className="text-2xs uppercase tracking-widest text-muted font-mono">reports</p>
          <h1 className="mt-1.5 font-display text-3xl sm:text-4xl font-semibold text-primary tracking-tightest leading-[1.05]">
            Investigation outputs,
            <span className="bg-gradient-to-r from-accent via-accent-soft to-accent bg-clip-text text-transparent">
              {" "}
              when they exist.
            </span>
          </h1>
          <p className="mt-2 text-sm text-secondary max-w-2xl leading-relaxed">
            This page is a real report hub, not a placeholder. Pick a query, inspect any saved
            report, or generate a new one from the existing backend route.
          </p>
        </div>
        <Link
          to="/app/queries"
          className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-4 py-2 text-sm font-medium text-primary transition-colors hover:border-edge-bright"
        >
          Open queries
          <ArrowRight size={14} />
        </Link>
      </div>

      <Section icon={NotebookText} title="Saved report viewer" hint="query selection on the left, report output on the right">
        <div className="grid gap-0 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="border-b border-edge lg:border-b-0 lg:border-r">
            <div className="px-4 py-3 border-b border-edge">
              <p className="text-2xs uppercase tracking-widest text-muted font-mono">recent queries</p>
              <p className="mt-1 text-xs text-secondary">
                Select a fingerprint to inspect the saved report or create a new one.
              </p>
            </div>
            {queriesLoading ? (
              <div className="p-4 space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : queries.length === 0 ? (
              <div className="p-6 text-center text-sm text-muted">
                No queries are available yet. Run the collector to populate reports.
              </div>
            ) : (
              <div className="max-h-[560px] overflow-y-auto">
                {queries.map((query) => {
                  const active = query.id === selectedId;
                  return (
                    <button
                      key={query.id}
                      onClick={() => setSelectedId(query.id)}
                      className={`w-full border-b border-edge px-4 py-3 text-left transition-colors ${
                        active ? "bg-accent/5" : "hover:bg-panel-2/60"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm text-primary font-mono">
                          {query.normalized_query}
                        </p>
                        <span className="rounded-full border border-edge px-2 py-0.5 text-2xs font-mono uppercase tracking-widest text-muted">
                          {query.regression_count} regs
                        </span>
                      </div>
                      <p className="mt-2 text-2xs font-mono uppercase tracking-widest text-muted">
                        {(query.latest_mean_ms ?? 0).toFixed(2)}ms · {query.latest_calls?.toLocaleString() ?? "—"} calls
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-5 space-y-4">
            {!hasQuery ? (
              <div className="rounded-2xl border border-dashed border-edge bg-panel-2/40 px-4 py-8 text-sm text-muted">
                No query selected. Choose a fingerprint from the list to inspect its report.
              </div>
            ) : reportLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : reportError || !report ? (
              <div className="rounded-2xl border border-edge bg-panel-2/60 p-5 space-y-4">
                <div>
                  <p className="text-2xs uppercase tracking-widest text-muted font-mono">no saved report</p>
                  <p className="mt-2 text-sm text-secondary leading-relaxed">
                    PlanTrace has no stored report for this query yet. Generate one from the
                    current backend route or open the query detail page for the investigator panel.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={generateMutation.isPending}
                    onClick={() => generateMutation.mutate()}
                    className="inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-accent-soft disabled:opacity-50"
                  >
                    {generateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Generate report
                  </button>
                  <Link
                    to={`/app/queries/${selectedId}`}
                    className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-4 py-2 text-sm font-medium text-primary transition-colors hover:border-edge-bright"
                  >
                    Open query
                  </Link>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono">model</p>
                    <p className="mt-2 text-sm text-primary">{report.model_name ?? "deterministic"}</p>
                  </div>
                  <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono">findings</p>
                    <p className="mt-2 text-sm text-primary">{findingsCount} items</p>
                  </div>
                  <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
                    <p className="text-2xs uppercase tracking-widest text-muted font-mono">source</p>
                    <p className="mt-2 text-sm text-primary">saved report</p>
                  </div>
                </div>
                <div className="rounded-2xl border border-edge bg-panel-2/60 p-5">
                  <p className="text-2xs uppercase tracking-widest text-muted font-mono">generated text</p>
                  <pre className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-secondary font-sans">
                    {report.generated_text}
                  </pre>
                </div>
                <div className="rounded-2xl border border-edge bg-panel-2/60 p-5">
                  <p className="text-2xs uppercase tracking-widest text-muted font-mono">findings</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {report.findings.findings.map((finding) => (
                      <span
                        key={finding}
                        className="inline-flex items-center gap-1 rounded-full border border-edge bg-panel px-3 py-1.5 text-xs text-secondary"
                      >
                        <Sparkles size={11} className="text-accent" />
                        {finding}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={generateMutation.isPending}
                    onClick={() => generateMutation.mutate()}
                    className="inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-accent-soft disabled:opacity-50"
                  >
                    {generateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Regenerate report
                  </button>
                  <Link
                    to={`/app/queries/${selectedId}`}
                    className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-4 py-2 text-sm font-medium text-primary transition-colors hover:border-edge-bright"
                  >
                    Open query detail
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </Section>
    </div>
  );
}
