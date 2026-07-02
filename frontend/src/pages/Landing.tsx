import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Database,
  GitBranch,
  Github,
  LayoutGrid,
  Layers3,
  Monitor,
  Play,
  ShieldCheck,
  Sparkles,
  Timer,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCollectorStatus, useQueries, useRegressions } from "../api/hooks";
import { MetricCard } from "../components/MetricCard";
import { Section } from "../components/Section";
import { Spotlight } from "../components/Spotlight";
import { landingDemo } from "../data/demo";

type PreviewMode = "demo" | "live";

function Panel({
  title,
  value,
  hint,
  tone = "neutral",
}: {
  title: string;
  value: string;
  hint: string;
  tone?: "neutral" | "warn" | "bad" | "ok";
}) {
  const toneClass =
    tone === "warn"
      ? "border-warn/20 bg-warn/10"
      : tone === "bad"
        ? "border-bad/20 bg-bad/10"
        : tone === "ok"
          ? "border-ok/20 bg-ok/10"
          : "border-edge bg-panel-2/60";

  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <p className="text-2xs uppercase tracking-widest text-muted font-mono">{title}</p>
      <p className="mt-2 text-xl font-display font-semibold text-primary tracking-tightest">
        {value}
      </p>
      <p className="mt-1 text-xs text-secondary leading-relaxed">{hint}</p>
    </div>
  );
}

function FeatureTile({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <Spotlight className="surface h-full" glow="rgba(245, 158, 11, 0.12)">
      <div className="p-5 h-full">
        <div className="flex items-center gap-3">
          <span className="grid place-items-center w-9 h-9 rounded-xl border border-edge bg-panel-2">
            <Icon size={16} className="text-accent" />
          </span>
          <h3 className="text-sm font-semibold text-primary">{title}</h3>
        </div>
        <p className="mt-3 text-sm text-secondary leading-relaxed">{description}</p>
      </div>
    </Spotlight>
  );
}

export function Landing() {
  const [mode, setMode] = useState<PreviewMode>("demo");
  const { data: queriesPage, isError: queriesError } = useQueries({ limit: 6, sort: "mean_latency_desc" });
  const { data: regressionsPage, isError: regressionsError } = useRegressions({ limit: 6 });
  const { data: collectorStatus } = useCollectorStatus();

  const liveQueries = queriesPage?.items ?? [];
  const liveRegressions = regressionsPage?.items ?? [];
  const liveAvailable = !queriesError && !regressionsError && (liveQueries.length > 0 || liveRegressions.length > 0);

  const preview = useMemo(() => {
    if (mode === "live" && liveAvailable) {
      const topQuery = liveQueries[0];
      const topRegression = liveRegressions[0];
      const avgLatency = liveQueries.length
        ? Number(
            (
              liveQueries.reduce((sum, q) => sum + (q.latest_mean_ms ?? 0), 0) /
              liveQueries.length
            ).toFixed(2)
          )
        : landingDemo.avgLatencyMs;

      return {
        queriesTracked: queriesPage?.total ?? landingDemo.queriesTracked,
        slowQueries: liveQueries.filter((q) => (q.latest_mean_ms ?? 0) > 100).length,
        criticalRegressions: liveRegressions.filter((r) => r.severity === "critical" || r.severity === "high").length,
        avgLatencyMs: avgLatency,
        topQuery:
          topQuery != null
            ? {
                fingerprintHash: topQuery.fingerprint_hash.slice(0, 16),
                normalizedQuery: topQuery.normalized_query,
                latestMeanMs: topQuery.latest_mean_ms ?? 0,
                latestCalls: topQuery.latest_calls ?? 0,
                regressionCount: topQuery.regression_count,
              }
            : landingDemo.topQuery,
        topRegression:
          topRegression != null
            ? {
                severity: topRegression.severity,
                regressionType: topRegression.regression_type,
                message: topRegression.message,
                confidence: 0.87,
              }
            : landingDemo.topRegression,
        placement: landingDemo.placement,
      };
    }

    return landingDemo;
  }, [liveAvailable, liveQueries, liveRegressions, mode, queriesPage?.total]);

  const collectorLabel = collectorStatus?.[0]?.status ?? "demo-ready";

  return (
    <div className="space-y-10 lg:space-y-12">
      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr] items-stretch">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1.5 text-2xs font-mono uppercase tracking-[0.3em] text-accent">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            {mode === "live" && liveAvailable ? "live preview" : "demo mode"}
          </div>

          <div className="space-y-4">
            <h1 className="max-w-3xl font-display text-4xl sm:text-5xl font-semibold text-primary tracking-tightest leading-[0.96]">
              Find query regressions before they become database incidents.
            </h1>
            <p className="max-w-2xl text-base sm:text-lg text-secondary leading-relaxed">
              PlanTrace turns SQL telemetry, plan diagnostics, workload placement simulation,
              and evidence-grounded investigation reports into one product surface. It stays
              explicit about synthetic placement and never pretends to control a real cluster.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/app?demo=1"
              className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-accent-soft"
            >
              Open Demo
              <Play size={14} />
            </Link>
            <Link
              to="/learn"
              className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-5 py-3 text-sm font-medium text-primary transition-colors hover:border-edge-bright"
            >
              View Architecture
              <ArrowRight size={14} />
            </Link>
            <a
              href="https://github.com/sushildalavi/plantrace"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-5 py-3 text-sm font-medium text-secondary transition-colors hover:border-edge-bright hover:text-primary"
            >
              GitHub
              <Github size={14} />
            </a>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Tracked queries"
              value={preview.queriesTracked}
              icon={Database}
              hint="fingerprints in the product story"
            />
            <MetricCard
              label="Slow queries"
              value={preview.slowQueries}
              icon={Timer}
              tone={preview.slowQueries > 0 ? "warn" : "ok"}
              hint="latest snapshot or demo sample"
            />
            <MetricCard
              label="Critical regs"
              value={preview.criticalRegressions}
              icon={AlertTriangle}
              tone={preview.criticalRegressions > 0 ? "bad" : "ok"}
              hint={`${preview.avgLatencyMs.toFixed(2)}ms average mean latency`}
            />
            <MetricCard
              label="Collector"
              value={collectorLabel}
              icon={Monitor}
              hint={liveAvailable ? "live local backend detected" : "demo preview active"}
            />
          </div>
        </div>

        <Spotlight className="surface h-full" glow="rgba(52, 211, 153, 0.10)">
          <div className="relative p-5 sm:p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">
                  interactive demo preview
                </p>
                <h2 className="mt-1 text-lg font-semibold text-primary">
                  Product story snapshot
                </h2>
              </div>
              <div className="inline-flex rounded-full border border-edge bg-panel-2 p-1">
                <button
                  className={`rounded-full px-3 py-1.5 text-2xs font-mono uppercase tracking-widest transition-colors ${
                    mode === "demo" ? "bg-ink text-primary ring-1 ring-edge" : "text-muted hover:text-primary"
                  }`}
                  onClick={() => setMode("demo")}
                >
                  Demo data
                </button>
                <button
                  className={`rounded-full px-3 py-1.5 text-2xs font-mono uppercase tracking-widest transition-colors disabled:opacity-40 ${
                    mode === "live" ? "bg-ink text-primary ring-1 ring-edge" : "text-muted hover:text-primary"
                  }`}
                  onClick={() => setMode("live")}
                  disabled={!liveAvailable}
                >
                  Live data
                </button>
              </div>
            </div>

            {mode === "demo" && (
              <div className="rounded-xl border border-accent/20 bg-accent/10 px-4 py-3 text-sm text-secondary">
                Demo mode is on. The preview uses bundled sample telemetry so reviewers can
                understand the product without setting up the collector.
              </div>
            )}
            {mode === "live" && liveAvailable && (
              <div className="rounded-xl border border-ok/20 bg-ok/10 px-4 py-3 text-sm text-secondary">
                Live preview is on. The cards below use the current backend snapshot when
                collector data is available.
              </div>
            )}

            <div className="grid gap-3">
              <Panel
                title="Slow query"
                value={`${preview.topQuery.latestMeanMs.toFixed(1)} ms`}
                hint={`${preview.topQuery.latestCalls.toLocaleString()} calls · ${preview.topQuery.regressionCount} regressions · ${preview.topQuery.fingerprintHash}`}
                tone={preview.topQuery.latestMeanMs > 150 ? "warn" : "neutral"}
              />
              <Panel
                title="Regression risk"
                value={`${preview.topRegression.severity.toUpperCase()} · ${Math.round((preview.topRegression.confidence ?? 0.91) * 100)}%`}
                hint={`${preview.topRegression.regressionType} · ${preview.topRegression.message}`}
                tone={preview.topRegression.severity === "high" ? "bad" : "warn"}
              />
              <Panel
                title="Placement comparison"
                value={`${preview.placement.overloadedBefore} → ${preview.placement.overloadedAfter} overloaded nodes`}
                hint={`${(preview.placement.hotspotReduction * 100).toFixed(0)}% hotspot reduction · ${preview.placement.decisionP95.toFixed(1)}ms decision p95`}
                tone="ok"
              />
            </div>
          </div>
        </Spotlight>
      </section>

      <Section
        icon={Sparkles}
        title="The problem PlanTrace solves"
        hint="slow queries, regressions, bad plans, hotspots, and placement tradeoffs"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5 p-5">
          {[
            {
              icon: Database,
              title: "Slow queries hidden in traffic",
              description: "Surface fingerprints whose latest execution time drifts away from the rest of the workload.",
            },
            {
              icon: GitBranch,
              title: "Recurring SQL regressions",
              description: "Track repeat offenders across consecutive collector runs instead of guessing from a single EXPLAIN.",
            },
            {
              icon: AlertTriangle,
              title: "Poor query plans",
              description: "Call out sequential scans, row estimate mismatches, and access-path flips with evidence attached.",
            },
            {
              icon: LayoutGrid,
              title: "Workload hotspots",
              description: "Compare synthetic placement strategies and understand where overload shifts under different policies.",
            },
            {
              icon: ShieldCheck,
              title: "Evidence over hype",
              description: "Every report is grounded in collected telemetry and explicitly labels synthetic placement analysis.",
            },
          ].map((item) => (
            <FeatureTile key={item.title} icon={item.icon} title={item.title} description={item.description} />
          ))}
        </div>
      </Section>

      <Section
        icon={Workflow}
        title="How it works"
        hint="collector to observability, with the app staying honest about each layer"
      >
        <div className="p-5">
          <div className="grid gap-3 lg:grid-cols-6">
            {landingDemo.pipeline.map((step, index) => (
              <div key={step} className="relative">
                <div className="rounded-2xl border border-edge bg-panel-2/70 p-4 min-h-[104px]">
                  <p className="text-2xs uppercase tracking-widest text-muted font-mono">
                    step {index + 1}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-primary">{step}</p>
                  <p className="mt-2 text-xs text-secondary leading-relaxed">
                    {index === 0 && "Captures query metrics and plans from the source workload."}
                    {index === 1 && "Streams telemetry through a durable event pipe."}
                    {index === 2 && "Persists query snapshots, diagnostics, and regressions."}
                    {index === 3 && "Serves the diagnostics and investigation API."}
                    {index === 4 && "Presents the product site and dashboard to reviewers."}
                    {index === 5 && "Publishes the operational view without inventing throughput."}
                  </p>
                </div>
                {index < landingDemo.pipeline.length - 1 && (
                  <ArrowRight
                    size={14}
                    className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 text-muted"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Section icon={Layers3} title="Feature set" hint="the app is a serious database observability tool">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 p-5">
          <FeatureTile
            icon={Database}
            title="Query telemetry"
            description="Track fingerprints, call counts, latency, and plan snapshots across collector runs."
          />
          <FeatureTile
            icon={AlertTriangle}
            title="Regression detection"
            description="Identify regressions from deterministic rules, then surface the evidence trail behind each finding."
          />
          <FeatureTile
            icon={GitBranch}
            title="Plan diagnostics"
            description="Flag scan changes, row estimate drift, and expensive plans with concrete observations."
          />
          <FeatureTile
            icon={LayoutGrid}
            title="Placement simulation"
            description="Compare synthetic workload placement strategies without claiming control over real production clusters."
          />
          <FeatureTile
            icon={Sparkles}
            title="Evidence-grounded investigation"
            description="If AI is enabled, reports are constrained by collected signals and fall back when evidence is thin."
          />
          <FeatureTile
            icon={BarChart3}
            title="Observability metrics"
            description="Tie query behavior back to the product’s collector, API, and dashboard telemetry."
          />
        </div>
      </Section>

      <Section
        icon={LayoutGrid}
        title="Architecture"
        hint="clean service map, no decorative noise"
      >
        <div className="p-5 space-y-4">
          <div className="grid gap-3 lg:grid-cols-3">
            {[
              {
                title: "Ingest",
                body: "C++ collector, Kafka, PostgreSQL",
                detail: "Captures query snapshots and stores historical context for diagnostics.",
              },
              {
                title: "Analysis",
                body: "FastAPI, deterministic rules, reports",
                detail: "Produces regressions, recommendations, and evidence-grounded investigation output.",
              },
              {
                title: "Presentation",
                body: "React dashboard, landing site, docs",
                detail: "Lets reviewers inspect the platform without hiding behind unsupported claims.",
              },
            ].map((item) => (
              <div key={item.title} className="rounded-2xl border border-edge bg-panel-2/60 p-4">
                <p className="text-2xs uppercase tracking-widest text-muted font-mono">{item.title}</p>
                <p className="mt-2 text-base font-semibold text-primary">{item.body}</p>
                <p className="mt-2 text-sm text-secondary leading-relaxed">{item.detail}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Panel
              title="Route"
              value="/app"
              hint="workspace entry point with overview, queries, regressions, placement, and reports"
            />
            <Panel
              title="Route"
              value="/learn"
              hint="architecture and demo explanation page for reviewers"
            />
            <Panel
              title="Route"
              value="/app?demo=1"
              hint="explicit demo mode banner for guided review"
            />
          </div>
        </div>
      </Section>

      <Section
        icon={ShieldCheck}
        title="Validation"
        hint="real local checks, no invented throughput claims"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 p-5">
          {landingDemo.validation.map((item) => (
            <div key={item.label} className="rounded-2xl border border-edge bg-panel-2/60 p-4">
              <p className="text-2xs uppercase tracking-widest text-muted font-mono">{item.label}</p>
              <p className="mt-2 text-lg font-semibold text-primary">{item.value}</p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
