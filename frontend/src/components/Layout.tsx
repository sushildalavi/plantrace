import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Github,
  LayoutGrid,
  NotebookText,
  Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { CommandPalette } from "./CommandPalette";
import { useCollectorStatus } from "../api/hooks";

function LivePulse() {
  return (
    <span className="relative inline-grid place-items-center w-2 h-2">
      <span className="absolute inset-0 rounded-full bg-ok animate-pulse-ring" />
      <span className="relative w-1.5 h-1.5 rounded-full bg-ok" />
    </span>
  );
}

function NavItem({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: LucideIcon;
}) {
  return (
    <NavLink
      to={to}
      end={to === "/app"}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
          isActive
            ? "bg-panel-2 text-primary ring-1 ring-edge"
            : "text-secondary hover:text-primary hover:bg-panel-2/60"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={`grid place-items-center w-8 h-8 rounded-lg ring-1 transition-colors ${
              isActive ? "bg-ink ring-edge-bright" : "bg-panel ring-edge"
            }`}
          >
            <Icon
              size={15}
              className={isActive ? "text-accent" : "text-muted group-hover:text-secondary"}
            />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium text-left">{label}</span>
            <span className="block text-2xs font-mono uppercase tracking-widest text-muted">
              {to}
            </span>
          </span>
        </>
      )}
    </NavLink>
  );
}

function SectionLink({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: LucideIcon;
}) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-2 rounded-full border border-edge bg-panel-2 px-3 py-1.5 text-2xs font-mono uppercase tracking-widest text-muted transition-colors hover:border-edge-bright hover:text-primary"
    >
      <Icon size={11} className="text-accent" />
      {label}
    </Link>
  );
}

export function Layout() {
  const { pathname, search } = useLocation();
  const [now, setNow] = useState<string>("");
  const demoMode = new URLSearchParams(search).get("demo") === "1";
  const { data: collectorStatus } = useCollectorStatus();
  const collectorStatusItem = collectorStatus?.[0];

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setNow(
        d.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const collectorLabel = useMemo(() => {
    const status = collectorStatus?.[0];
    if (!status) return "collector unknown";
    return `${status.environment} · ${status.status}`;
  }, [collectorStatus]);

  const nav = [
    { to: "/app", label: "Overview", icon: Activity },
    { to: "/app/queries", label: "Queries", icon: Search },
    { to: "/app/regressions", label: "Regressions", icon: AlertTriangle },
    { to: "/app/placement", label: "Placement", icon: LayoutGrid },
    { to: "/app/reports", label: "Reports", icon: NotebookText },
    { to: "/learn", label: "Learn", icon: BarChart3 },
  ];

  return (
    <div className="min-h-screen">
      <aside className="hidden xl:fixed xl:inset-y-0 xl:z-30 xl:flex xl:w-[292px] xl:flex-col xl:border-r xl:border-edge xl:bg-panel/95 xl:backdrop-blur">
        <div className="flex h-full flex-col">
          <div className="px-5 pt-5 pb-4 border-b border-edge">
            <NavLink to="/" className="flex items-center gap-2.5 group">
              <span className="relative grid place-items-center w-9 h-9 rounded-xl bg-gradient-to-br from-accent/20 to-accent/0 ring-1 ring-accent/25 transition-all group-hover:ring-accent/60">
                <span className="font-mono font-bold text-accent text-[11px] tracking-tighter">
                  PT
                </span>
              </span>
              <span>
                <span className="block font-display text-sm font-semibold text-primary tracking-tightest">
                  PlanTrace
                </span>
                <span className="block text-2xs text-muted font-mono uppercase tracking-widest">
                  agentic sql intelligence
                </span>
              </span>
            </NavLink>

            <div className="mt-4 space-y-2">
              <div className="flex flex-wrap gap-2">
                <SectionLink to="/app?demo=1" label="Open demo" icon={Activity} />
                <SectionLink to="/learn" label="Architecture" icon={BarChart3} />
              </div>
              <div className="rounded-xl border border-edge bg-panel-2/70 px-3 py-2.5 text-xs text-secondary">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono uppercase tracking-widest text-muted">workspace</span>
                  <span
                    className={`inline-flex items-center gap-1.5 text-2xs font-mono uppercase tracking-widest ${
                      collectorStatusItem ? "text-ok" : "text-muted"
                    }`}
                  >
                    {collectorStatusItem ? <LivePulse /> : <span className="w-1.5 h-1.5 rounded-full bg-muted" />}
                    {collectorStatusItem ? "live" : "offline"}
                  </span>
                </div>
                <p className="mt-2 leading-relaxed">
                  Query telemetry, regression detection, placement simulation, and reports in one surface.
                </p>
              </div>
            </div>
          </div>

          <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
            {nav.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </nav>

          <div className="px-5 pb-5 pt-3 border-t border-edge space-y-3">
            <div className="rounded-xl border border-edge bg-panel-2/70 px-3 py-2.5 text-xs text-secondary">
              <p className="font-mono uppercase tracking-widest text-muted">status</p>
              <p className="mt-1 text-sm text-primary">{collectorLabel}</p>
              <p className="mt-1 text-2xs font-mono uppercase tracking-widest text-muted">
                {pathname.startsWith("/app") ? "dashboard workspace" : "site shell"}
              </p>
            </div>
            <a
              href="https://github.com/sushildalavi/plantrace"
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-full items-center justify-between rounded-xl border border-edge bg-panel-2 px-3 py-2.5 text-sm text-secondary transition-colors hover:border-edge-bright hover:text-primary"
            >
              <span className="inline-flex items-center gap-2">
                <Github size={14} className="text-muted" />
                GitHub
              </span>
              <span className="font-mono text-2xs uppercase tracking-widest text-muted">
                repo
              </span>
            </a>
          </div>
        </div>
      </aside>

      <div className="xl:pl-[292px]">
        <header className="sticky top-0 z-20 border-b border-edge bg-ink/90 backdrop-blur supports-[backdrop-filter]:bg-ink/75">
          <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
            <div className="xl:hidden">
              <NavLink to="/" className="flex items-center gap-2.5">
                <span className="grid place-items-center w-8 h-8 rounded-lg bg-panel-2 ring-1 ring-edge">
                  <span className="font-mono font-bold text-accent text-[11px] tracking-tighter">
                    PT
                  </span>
                </span>
                <span>
                  <span className="block font-display text-sm font-semibold text-primary tracking-tightest">
                    PlanTrace
                  </span>
                  <span className="block text-2xs text-muted font-mono uppercase tracking-widest">
                    workspace
                  </span>
                </span>
              </NavLink>
            </div>

            <div className="hidden lg:flex items-center gap-2 text-2xs font-mono uppercase tracking-widest text-muted">
              <span className="rounded-full border border-edge bg-panel-2 px-2.5 py-1 text-primary">
                /app
              </span>
              <span className="text-muted">Agentic SQL diagnostics</span>
            </div>

            <div className="ml-auto flex items-center gap-2 sm:gap-3">
              {demoMode && (
                <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-2.5 py-1 text-2xs font-mono uppercase tracking-widest text-accent">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  demo mode
                </span>
              )}
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-edge bg-panel-2 px-2.5 py-1 text-2xs font-mono uppercase tracking-widest text-muted">
                <LivePulse />
                {collectorLabel}
              </span>
              <span className="hidden sm:inline-flex rounded-full border border-edge bg-panel-2 px-2.5 py-1 text-2xs font-mono uppercase tracking-widest text-muted">
                {now}
              </span>
              <CommandPalette />
              <a
                href="https://github.com/sushildalavi/plantrace"
                target="_blank"
                rel="noreferrer"
                className="grid place-items-center w-9 h-9 rounded-lg border border-edge bg-panel-2 text-secondary transition-colors hover:border-edge-bright hover:text-primary"
                aria-label="github"
              >
                <Github size={14} />
              </a>
            </div>
          </div>
          {demoMode && (
            <div className="border-t border-edge bg-accent/10 px-4 py-2 text-center text-2xs font-mono uppercase tracking-[0.3em] text-accent sm:hidden">
              demo mode enabled
            </div>
          )}
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 sm:px-6 py-6 sm:py-8 animate-fade-in">
          <Outlet />
        </main>

        <footer className="border-t border-edge bg-panel/60 px-4 sm:px-6 py-4">
          <div className="mx-auto flex max-w-7xl flex-col gap-2 text-2xs text-muted font-mono sm:flex-row sm:items-center sm:justify-between">
            <span>PlanTrace · C++ collector · Kafka · PostgreSQL · FastAPI · React</span>
            <span>synthetic placement simulation · evidence-grounded reporting</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
