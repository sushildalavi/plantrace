import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Activity,
  ArrowRight,
  BarChart3,
  Database,
  Hash,
  Play,
  Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCollect, useQueries, useRegressions } from "../api/hooks";

interface Item {
  id: string;
  label: string;
  hint?: string;
  icon: LucideIcon;
  group: string;
  onRun: () => void | Promise<void>;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const collectMutation = useCollect();
  const { data: queriesPage } = useQueries({ limit: 80, sort: "mean_latency_desc" });
  const { data: regsPage } = useRegressions({ limit: 50 });

  // open on cmd/ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "/" && document.activeElement === document.body) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const items: Item[] = useMemo(() => {
    const navItems: Item[] = [
      {
        id: "nav:landing",
        label: "Go to landing",
        hint: "/",
        icon: Activity,
        group: "navigate",
        onRun: () => navigate("/"),
      },
      {
        id: "nav:app",
        label: "Go to app",
        hint: "/app",
        icon: Database,
        group: "navigate",
        onRun: () => navigate("/app"),
      },
      {
        id: "nav:queries",
        label: "Go to queries",
        hint: "/app/queries",
        icon: Hash,
        group: "navigate",
        onRun: () => navigate("/app/queries"),
      },
      {
        id: "nav:placement",
        label: "Go to placement",
        hint: "/app/placement",
        icon: ArrowRight,
        group: "navigate",
        onRun: () => navigate("/app/placement"),
      },
      {
        id: "nav:regressions",
        label: "Go to regressions",
        hint: "/app/regressions",
        icon: AlertTriangle,
        group: "navigate",
        onRun: () => navigate("/app/regressions"),
      },
      {
        id: "nav:reports",
        label: "Go to reports",
        hint: "/app/reports",
        icon: Hash,
        group: "navigate",
        onRun: () => navigate("/app/reports"),
      },
      {
        id: "nav:learn",
        label: "Go to learn",
        hint: "/learn",
        icon: BarChart3,
        group: "navigate",
        onRun: () => navigate("/learn"),
      },
    ];
    const actions: Item[] = [
      {
        id: "act:collect",
        label: "Run collector",
        hint: "POST /api/collect/run",
        icon: Play,
        group: "actions",
        onRun: async () => {
          await collectMutation.mutateAsync();
        },
      },
    ];
    const queries: Item[] = (queriesPage?.items ?? []).map((qq) => ({
      id: `q:${qq.id}`,
      label: qq.normalized_query.slice(0, 80),
      hint:
        (qq.latest_mean_ms != null ? `${qq.latest_mean_ms.toFixed(2)}ms` : "—") +
        " · " +
        (qq.latest_calls?.toLocaleString() ?? "—") +
        " calls",
      icon: Database,
      group: "queries",
      onRun: () => navigate(`/app/queries/${qq.id}`),
    }));
    const regs: Item[] = (regsPage?.items ?? []).slice(0, 30).map((r) => ({
      id: `r:${r.id}`,
      label: r.message,
      hint: r.regression_type + " · " + r.severity,
      icon: AlertTriangle,
      group: "regressions",
      onRun: () => navigate(`/app/queries/${r.fingerprint_id}`),
    }));
    return [...navItems, ...actions, ...queries, ...regs];
  }, [queriesPage, regsPage, navigate, collectMutation]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return items;
    return items.filter(
      (it) =>
        it.label.toLowerCase().includes(term) ||
        it.group.toLowerCase().includes(term) ||
        (it.hint && it.hint.toLowerCase().includes(term))
    );
  }, [items, q]);

  // group filtered by group preserving order
  const grouped = useMemo(() => {
    const out: { group: string; items: Item[] }[] = [];
    const seen = new Map<string, Item[]>();
    for (const it of filtered) {
      if (!seen.has(it.group)) seen.set(it.group, []);
      seen.get(it.group)!.push(it);
    }
    for (const [group, items] of seen) out.push({ group, items });
    return out;
  }, [filtered]);

  // active item refers to flat index in `filtered`
  useEffect(() => {
    setActive(0);
  }, [q]);

  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="hidden md:inline-flex items-center gap-2 px-2.5 py-1.5 surface-2 hover:border-edge-bright text-2xs text-muted hover:text-secondary transition-colors group"
        aria-label="open command palette"
      >
        <Search size={12} />
        <span>Search</span>
        <kbd className="ml-2 px-1.5 py-0.5 bg-ink ring-1 ring-edge rounded text-[10px] font-mono text-muted group-hover:text-secondary">
          ⌘K
        </kbd>
      </button>
    );
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const it = filtered[active];
      if (it) {
        Promise.resolve(it.onRun()).finally(() => setOpen(false));
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4 animate-fade-in"
      onClick={() => setOpen(false)}
    >
      <div
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        aria-hidden
      />
      <div
        className="relative w-full max-w-xl surface shadow-glow animate-scale-in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3.5 py-3 border-b border-edge">
          <Search size={14} className="text-muted shrink-0" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search queries, regressions, or actions…"
            className="flex-1 bg-transparent outline-none text-sm text-primary placeholder:text-muted"
          />
          <kbd className="px-1.5 py-0.5 bg-ink ring-1 ring-edge rounded text-[10px] font-mono text-muted">
            esc
          </kbd>
        </div>
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted">
              No results.
            </div>
          ) : (
            grouped.map(({ group, items }) => {
              return (
                <div key={group}>
                  <div className="px-3.5 pt-2 pb-1 text-2xs uppercase tracking-widest text-muted font-mono">
                    {group}
                  </div>
                  {items.map((it) => {
                    const flatIdx = filtered.indexOf(it);
                    const isActive = flatIdx === active;
                    return (
                      <button
                        key={it.id}
                        data-idx={flatIdx}
                        onMouseEnter={() => setActive(flatIdx)}
                        onClick={() => {
                          Promise.resolve(it.onRun()).finally(() => setOpen(false));
                        }}
                        className={`w-full flex items-center gap-3 px-3.5 py-2 text-left transition-colors ${
                          isActive ? "bg-accent/10 text-primary" : "text-secondary"
                        }`}
                      >
                        <it.icon
                          size={14}
                          className={isActive ? "text-accent" : "text-muted"}
                        />
                        <span className="flex-1 text-sm truncate font-mono">
                          {it.label}
                        </span>
                        {it.hint && (
                          <span className="text-2xs text-muted font-mono whitespace-nowrap">
                            {it.hint}
                          </span>
                        )}
                        {isActive && (
                          <ArrowRight size={12} className="text-accent" />
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
        <div className="flex items-center justify-between px-3.5 py-2 border-t border-edge text-2xs text-muted font-mono">
          <span className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <kbd className="px-1 bg-panel-2 ring-1 ring-edge rounded text-[10px]">↑</kbd>
              <kbd className="px-1 bg-panel-2 ring-1 ring-edge rounded text-[10px]">↓</kbd>
              navigate
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="px-1 bg-panel-2 ring-1 ring-edge rounded text-[10px]">↵</kbd>
              select
            </span>
          </span>
          <span className="inline-flex items-center gap-1">
            <Hash size={10} />
            {filtered.length} result{filtered.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>
    </div>
  );
}
