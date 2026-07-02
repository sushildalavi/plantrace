import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Database, History, Timer, TrendingUp } from "lucide-react";
import { useCollectorStatus, useQueries, useRegressions } from "../api/hooks";
import { ActivityFeed } from "../components/ActivityFeed";
import { MetricCard } from "../components/MetricCard";
import { QueryTable } from "../components/QueryTable";
import { Section, Skeleton } from "../components/Section";

export function Queries() {
  const navigate = useNavigate();
  const { data: queriesPage, isLoading } = useQueries({
    limit: 75,
    sort: "mean_latency_desc",
  });
  const { data: regressionsPage } = useRegressions({ limit: 20 });
  const { data: collectorStatus } = useCollectorStatus();

  const queries = queriesPage?.items ?? [];
  const regressions = regressionsPage?.items ?? [];

  const summary = useMemo(() => {
    const slow = queries.filter((q) => (q.latest_mean_ms ?? 0) > 100).length;
    const totalLatency = queries.reduce((sum, q) => sum + (q.latest_mean_ms ?? 0), 0);
    return {
      total: queriesPage?.total ?? 0,
      slow,
      avgLatency: queries.length ? Number((totalLatency / queries.length).toFixed(2)) : null,
      high: regressions.filter((r) => r.severity === "high" || r.severity === "critical").length,
    };
  }, [queries, queriesPage?.total, regressions]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between animate-fade-up">
        <div>
          <p className="text-2xs uppercase tracking-widest text-muted font-mono">queries</p>
          <h1 className="mt-1.5 font-display text-3xl sm:text-4xl font-semibold text-primary tracking-tightest leading-[1.05]">
            Telemetry that explains
            <span className="bg-gradient-to-r from-accent via-accent-soft to-accent bg-clip-text text-transparent">
              {" "}
              why a query changed.
            </span>
          </h1>
          <p className="mt-2 text-sm text-secondary max-w-2xl leading-relaxed">
            This page focuses on fingerprints, query latency, and regression context so you can
            move from symptom to investigation without leaving the workspace.
          </p>
        </div>
        <div className="rounded-full border border-edge bg-panel-2 px-3 py-2 text-2xs font-mono uppercase tracking-widest text-muted">
          collector {collectorStatus?.[0]?.status ?? "unknown"}
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <MetricCard
          label="Tracked queries"
          value={summary.total}
          icon={Database}
          hint="unique fingerprints in scope"
        />
        <MetricCard
          label="Slow queries"
          value={summary.slow}
          icon={Timer}
          tone={summary.slow > 0 ? "warn" : "ok"}
          hint="latest mean latency over 100ms"
        />
        <MetricCard
          label="High/Critical"
          value={summary.high}
          icon={AlertTriangle}
          tone={summary.high > 0 ? "bad" : "ok"}
          hint="regressions linked to tracked fingerprints"
        />
        <MetricCard
          label="Avg mean latency"
          value={summary.avgLatency}
          icon={TrendingUp}
          unit="ms"
          decimals={2}
          hint="across the current query set"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.75fr)]">
        <Section
          icon={Database}
          title="Query table"
          hint="search, sort, and open a fingerprint to inspect the detail view"
        >
          {isLoading ? (
            <div className="p-5 space-y-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <QueryTable rows={queries} onRowClick={(id) => navigate(`/app/queries/${id}`)} />
          )}
        </Section>

        <Section
          icon={History}
          title="Recent activity"
          hint="regressions and snapshot events stitched into one timeline"
        >
          {isLoading ? (
            <div className="p-5 space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (
            <ActivityFeed
              queries={queries}
              regressions={regressions}
              limit={10}
              onRegressionClick={(fid) => navigate(`/app/queries/${fid}`)}
            />
          )}
        </Section>
      </div>
    </div>
  );
}
