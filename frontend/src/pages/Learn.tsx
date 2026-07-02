import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Database,
  Layers3,
  ServerCog,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { Section } from "../components/Section";
import { landingDemo } from "../data/demo";

function RouteCard({
  path,
  title,
  description,
}: {
  path: string;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
      <p className="text-2xs uppercase tracking-widest text-muted font-mono">{path}</p>
      <h3 className="mt-2 text-sm font-semibold text-primary">{title}</h3>
      <p className="mt-2 text-sm text-secondary leading-relaxed">{description}</p>
    </div>
  );
}

export function Learn() {
  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1.5 text-2xs font-mono uppercase tracking-[0.3em] text-accent">
          <ShieldCheck size={11} />
          product walkthrough
        </div>
        <h1 className="max-w-3xl font-display text-4xl sm:text-5xl font-semibold text-primary tracking-tightest leading-[0.96]">
          A clear explanation of the architecture, demo flow, and supported claims.
        </h1>
        <p className="max-w-3xl text-base text-secondary leading-relaxed">
          This page is intentionally plain: it tells reviewers how data moves through the
          system, what the public landing page demonstrates, and how to get to the actual
          workspace without having to reverse-engineer the repo.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/app"
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-accent-soft"
          >
            Open app
            <ArrowRight size={14} />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-5 py-3 text-sm font-medium text-primary transition-colors hover:border-edge-bright"
          >
            Back to landing
          </Link>
        </div>
      </section>

      <Section icon={Workflow} title="System flow" hint="collector to observability">
        <div className="grid gap-3 p-5 lg:grid-cols-6">
          {landingDemo.pipeline.map((step, index) => (
            <div key={step} className="rounded-2xl border border-edge bg-panel-2/60 p-4">
              <p className="text-2xs uppercase tracking-widest text-muted font-mono">
                phase {index + 1}
              </p>
              <p className="mt-2 text-sm font-semibold text-primary">{step}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={Database} title="What the app exposes" hint="public routes and workspace entry points">
        <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-4">
          <RouteCard
            path="/"
            title="Landing page"
            description="Explains the product, shows the demo preview, and links reviewers into the workspace."
          />
          <RouteCard
            path="/app"
            title="Workspace overview"
            description="The dashboard entry point for query telemetry, trends, and high-severity regressions."
          />
          <RouteCard
            path="/app/queries"
            title="Query telemetry"
            description="Fingerprint detail, plan history, diagnostics, reports, and evidence-grounded investigation."
          />
          <RouteCard
            path="/app/regressions"
            title="Regression feed"
            description="Deterministic detections ordered by severity with direct links back to the query."
          />
          <RouteCard
            path="/app/placement"
            title="Placement simulator"
            description="Synthetic what-if workload placement comparison, clearly labeled as non-production."
          />
          <RouteCard
            path="/app/reports"
            title="Reports"
            description="Generated report outputs and a viewer for the latest saved investigation text."
          />
          <RouteCard
            path="/learn"
            title="This page"
            description="The architecture and demo guide for reviewers who want the reasoning before the clicks."
          />
          <RouteCard
            path="/app?demo=1"
            title="Demo mode"
            description="A visible banner and onboarding path so the product can be reviewed without setup."
          />
        </div>
      </Section>

      <Section icon={Layers3} title="Supported claims" hint="what the product does and does not say">
        <div className="grid gap-3 p-5 lg:grid-cols-2">
          <div className="rounded-2xl border border-edge bg-panel-2/60 p-4 space-y-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">we do say</p>
            <ul className="space-y-2 text-sm text-secondary leading-relaxed">
              <li>PlanTrace collects SQL telemetry and plan snapshots.</li>
              <li>Regression rules flag slowdowns and plan-shape changes.</li>
              <li>Placement analysis is synthetic and framed as what-if simulation.</li>
              <li>Investigation reports remain grounded in collected evidence.</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-edge bg-panel-2/60 p-4 space-y-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">we do not say</p>
            <ul className="space-y-2 text-sm text-secondary leading-relaxed">
              <li>We do not claim real control over a production cluster.</li>
              <li>We do not imply Azure SQL or any specific tenant placement is real.</li>
              <li>We do not invent throughput, latency, or operational outcomes.</li>
              <li>We do not hide demo fixtures behind ambiguous wording.</li>
            </ul>
          </div>
        </div>
      </Section>

      <Section icon={ServerCog} title="Local setup pointer" hint="for contributors and reviewers">
        <div className="grid gap-3 p-5 md:grid-cols-3">
          <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">backend</p>
            <p className="mt-2 text-sm text-secondary leading-relaxed">
              Start the FastAPI service, collector, and Postgres stack from the repo root.
            </p>
          </div>
          <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">frontend</p>
            <p className="mt-2 text-sm text-secondary leading-relaxed">
              Run the React app to inspect the landing page, workspace, and demo mode banner.
            </p>
          </div>
          <div className="rounded-2xl border border-edge bg-panel-2/60 p-4">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">validation</p>
            <p className="mt-2 text-sm text-secondary leading-relaxed">
              See the landing page validation cards for the current verified local checks.
            </p>
          </div>
        </div>
      </Section>

      <Section icon={BarChart3} title="Validation snapshot" hint="the repo checks that back the public claims">
        <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
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
