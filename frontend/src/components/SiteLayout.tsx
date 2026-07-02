import { useMemo } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ArrowRight, Github } from "lucide-react";

function TopLink({
  to,
  label,
}: {
  to: string;
  label: string;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-full px-3 py-1.5 text-2xs font-mono uppercase tracking-widest transition-colors ${
          isActive ? "bg-panel-2 text-primary ring-1 ring-edge" : "text-muted hover:text-primary"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export function SiteLayout() {
  const year = useMemo(() => new Date().getFullYear(), []);
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 border-b border-edge bg-ink/82 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="relative grid place-items-center w-8 h-8 rounded-lg bg-gradient-to-br from-accent/20 to-accent/0 ring-1 ring-accent/25">
              <span className="font-mono font-bold text-accent text-[11px] tracking-tighter">
                PT
              </span>
            </span>
            <span>
              <span className="block font-display text-sm font-semibold text-primary tracking-tightest">
                PlanTrace
              </span>
              <span className="block text-2xs text-muted font-mono uppercase tracking-widest">
                product cockpit
              </span>
            </span>
          </NavLink>

          <nav className="ml-auto hidden md:flex items-center gap-2">
            <TopLink to="/" label="Landing" />
            <TopLink to="/learn" label="Learn" />
            <TopLink to="/app" label="App" />
          </nav>

          <div className="ml-auto md:ml-0 flex items-center gap-2">
            <Link
              to="/app?demo=1"
              className="inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-xs font-medium text-ink transition-colors hover:bg-accent-soft"
            >
              Open demo
              <ArrowRight size={13} />
            </Link>
            <a
              href="https://github.com/sushildalavi/plantrace"
              target="_blank"
              rel="noreferrer"
              className="hidden sm:grid place-items-center w-9 h-9 rounded-lg border border-edge bg-panel-2 text-secondary transition-colors hover:border-edge-bright hover:text-primary"
              aria-label="github"
            >
              <Github size={14} />
            </a>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div key={pathname} className="animate-fade-up">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-edge bg-panel/55 px-4 sm:px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 text-2xs text-muted font-mono sm:flex-row sm:items-center sm:justify-between">
          <span>PlanTrace · SQL telemetry · regression diagnostics · workload placement</span>
          <span>{year} · local demo-ready product shell</span>
        </div>
      </footer>
    </div>
  );
}
