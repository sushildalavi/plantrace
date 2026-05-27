import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ChevronRight,
  Database,
  Gauge,
  ListOrdered,
  Play,
  Sparkles,
  Timer,
  TrendingUp,
} from "lucide-react";
import { useCollect, useCollectorStatus, useQueries, useRegressions } from "../api/hooks";
import { ActivityFeed } from "../components/ActivityFeed";
import { LatencyChart } from "../components/LatencyChart";
import { MetricCard } from "../components/MetricCard";
import { QueryTable } from "../components/QueryTable";
import { RegressionTypeIcon, regressionMeta } from "../components/RegressionTypeIcon";
import { Section, Skeleton } from "../components/Section";
import { SeverityBar } from "../components/SeverityBar";
import { Spotlight } from "../components/Spotlight";
import type { MetricPoint, RegressionListItem } from "../types";

function topRegressionTypes(items: RegressionListItem[]) {
  const counts = new Map<string, number>();
  for (const r of items) counts.set(r.regression_type, (counts.get(r.regression_type) ?? 0) + 1);
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
}

export function Dashboard() {
  const navigate = useNavigate();
  const [toast, setToast] = useState<string | null>(null);

  const { data: queriesPage, isLoading: qLoading } = useQueries({
    limit: 50,
    sort: "mean_latency_desc",
  });
  const { data: regAll } = useRegressions({ limit: 100 });
  const { data: collectorStatus } = useCollectorStatus();

  const collectMutation = useCollect();

  const handleCollect = async () => {
    try {
      const r = await collectMutation.mutateAsync();
      setToast(
        `collected ${r.fingerprints} queries · ${r.regressions} new regression${
          r.regressions === 1 ? "" : "s"
        } · ${r.duration_ms.toFixed(0)}ms`
      );
    } catch {
      setToast("collection failed — backend unreachable");
    }
  };

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const queries = queriesPage?.items ?? [];
  const regressions = regAll?.items ?? [];

  const totalQueries = queriesPage?.total ?? 0;
  const slowQueries = queries.filter((q) => (q.latest_mean_ms ?? 0) > 100).length;
  const totalRegs = regAll?.total ?? 0;

  const counts = useMemo(() => {
    const c: Record<"critical" | "high" | "medium" | "low", number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };
    for (const r of regressions) c[r.severity] = (c[r.severity] ?? 0) + 1;
    return c;
  }, [regressions]);

  const avgLatency = queries.length
    ? Number(
        (
          queries.reduce((s, q) => s + (q.latest_mean_ms ?? 0), 0) /
          queries.length
        ).toFixed(2)
      )
    : null;

  const latencyPoints: MetricPoint[] = queries
    .filter((q) => q.latest_mean_ms != null)
    .map((q) => ({
      captured_at: q.last_seen_at,
      mean_exec_time_ms: q.latest_mean_ms!,
      calls: q.latest_calls ?? 0,
      total_exec_time_ms: 0,
      rows_returned: 0,
      shared_blks_hit: 0,
      shared_blks_read: 0,
      temp_blks_written: 0,
    }))
    .sort((a, b) => a.captured_at.localeCompare(b.captured_at));

  const topTypes = topRegressionTypes(regressions);
  const topTypeMax = Math.max(1, ...topTypes.map(([, n]) => n));

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 animate-fade-up">
        <div>
          <p className="text-2xs uppercase tracking-widest text-muted font-mono">
            overview
          </p>
          <h1 className="font-display text-3xl sm:text-4xl font-semibold text-primary tracking-tightest mt-1.5 leading-[1.05]">
            Query performance,
            <br className="sm:hidden" />{" "}
            <span className="bg-gradient-to-r from-accent via-accent-soft to-accent bg-clip-text text-transparent">
              demystified.
            </span>
          </h1>
          <p className="text-secondary text-sm mt-2.5 max-w-xl leading-relaxed">
            Live signal from{" "}
            <span className="font-mono text-primary">pg_stat_statements</span>{" "}
            and <span className="font-mono text-primary">EXPLAIN</span>, scored by
            deterministic regression rules. No magic.
          </p>
        </div>
        <button
          onClick={handleCollect}
          disabled={collectMutation.isPending}
          className="group inline-flex items-center gap-2 px-4 py-2 bg-accent text-ink rounded-md text-sm font-medium hover:bg-accent-soft active:translate-y-px disabled:opacity-60 disabled:cursor-not-allowed transition-all shadow-glow"
        >
          <Play
            size={14}
            strokeWidth={2.75}
            className={
              collectMutation.isPending
                ? "animate-spin"
                : "group-active:scale-90 transition-transform"
            }
          />
          {collectMutation.isPending ? "Collecting…" : "Run collector"}
        </button>
      </div>

      {toast && (
        <div className="surface-2 px-4 py-2.5 text-sm text-secondary font-mono flex items-center gap-2 animate-slide-down">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          {toast}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 stagger-fast">
        <MetricCard
          label="Tracked queries"
          value={totalQueries}
          icon={Database}
          hint="unique fingerprints"
        />
        <MetricCard
          label="Slow ( >100ms )"
          value={slowQueries}
          icon={Timer}
          tone={slowQueries > 0 ? "warn" : "default"}
          hint="latest snapshot"
        />
        <MetricCard
          label="High/Critical regs"
          value={counts.high + counts.critical}
          icon={AlertTriangle}
          tone={counts.high + counts.critical > 0 ? "bad" : "default"}
          hint={`${totalRegs} total tracked`}
        />
        <MetricCard
          label="Avg mean latency"
          value={avgLatency}
          icon={Gauge}
          unit="ms"
          decimals={2}
          hint="across tracked"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-3">
        {latencyPoints.length > 1 && (
          <div className="lg:col-span-2">
            <Section
              icon={TrendingUp}
              title="Latency landscape"
              hint="latest mean per fingerprint"
            >
              <div className="px-5 pt-4 pb-2">
                <LatencyChart
                  points={latencyPoints}
                  dataKey="mean_exec_time_ms"
                  color="#f59e0b"
                  unit="ms"
                  height={220}
                />
              </div>
            </Section>
          </div>
        )}

        <Spotlight className="surface animate-fade-up" glow="rgba(245,158,11,0.14)">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-bad/0 via-bad/30 to-bad/0 opacity-60" />
          <div className="relative p-5">
            <div className="flex items-center gap-2.5">
              <span className="grid place-items-center w-6 h-6 rounded bg-panel-2 ring-1 ring-edge">
                <Sparkles size={13} className="text-secondary" />
              </span>
              <h2 className="text-sm font-semibold text-primary tracking-tight">
                Severity breakdown
              </h2>
            </div>
            <div className="mt-4">
              <SeverityBar high={counts.high} medium={counts.medium} low={counts.low} />
            </div>
            <div className="mt-5 space-y-2">
              <p className="text-2xs uppercase tracking-widest text-muted font-mono">
                top regression types
              </p>
              {topTypes.length === 0 ? (
                <p className="text-xs text-muted">none yet — run the collector.</p>
              ) : (
                <ul className="space-y-1.5 stagger-fast">
                  {topTypes.map(([type, n]) => {
                    const meta = regressionMeta(type);
                    const w = (n / topTypeMax) * 100;
                    return (
                      <li
                        key={type}
                        className="group flex items-center gap-2 cursor-pointer"
                        onClick={() => navigate("/regressions")}
                      >
                        <RegressionTypeIcon type={type} size={12} />
                        <span className="text-xs text-secondary group-hover:text-primary transition-colors truncate flex-1">
                          {meta.label}
                        </span>
                        <span className="relative h-1 w-16 bg-panel-2 rounded overflow-hidden shrink-0">
                          <span
                            className={`absolute left-0 top-0 h-full ${
                              meta.tone === "text-bad"
                                ? "bg-bad"
                                : meta.tone === "text-warn"
                                ? "bg-warn"
                                : "bg-secondary/50"
                            } transition-all duration-700`}
                            style={{ width: `${w}%` }}
                          />
                        </span>
                        <span className="text-2xs font-mono text-muted num w-6 text-right">
                          {n}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            <button
              onClick={() => navigate("/regressions")}
              className="mt-5 w-full inline-flex items-center justify-center gap-1 px-3 py-1.5 surface-2 hover:border-edge-bright text-xs text-secondary hover:text-primary transition-colors group"
            >
              browse all regressions
              <ChevronRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
          </div>
        </Spotlight>
      </div>

      <Section
        icon={AlertTriangle}
        title="Activity feed"
        hint={`snapshots/regressions · collector ${collectorStatus?.[0]?.status ?? "unknown"}`}
        action={
          <button
            onClick={() => navigate("/regressions")}
            className="text-2xs uppercase tracking-widest text-muted hover:text-secondary font-mono transition-colors"
          >
            view all →
          </button>
        }
      >
        {!regAll ? (
          <div className="space-y-2 p-5">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : regressions.length === 0 && queries.length === 0 ? (
          <div className="px-3 py-12 text-center">
            <p className="text-sm text-muted">
              No activity yet — run the collector after a workload change.
            </p>
            <p className="text-2xs text-muted mt-2 font-mono">
              tip: <span className="text-accent">make demo</span>
            </p>
          </div>
        ) : (
          <ActivityFeed
            queries={queries}
            regressions={regressions}
            limit={12}
            onRegressionClick={(fid) => navigate(`/queries/${fid}`)}
          />
        )}
      </Section>

      <Section
        icon={ListOrdered}
        title="Slowest queries"
        hint="ordered by mean exec time · click a row to drill in"
      >
        {qLoading ? (
          <div className="p-5 space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <QueryTable rows={queries} onRowClick={(id) => navigate(`/queries/${id}`)} />
        )}
      </Section>
    </div>
  );
}
