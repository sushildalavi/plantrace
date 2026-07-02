import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { useRegressions } from "../api/hooks";
import { RegressionBadge } from "../components/RegressionBadge";
import { RegressionTypeIcon, regressionMeta } from "../components/RegressionTypeIcon";
import { Section, Skeleton } from "../components/Section";

type Severity = "all" | "critical" | "high" | "medium" | "low";

const SEVERITIES: Severity[] = ["all", "critical", "high", "medium", "low"];

export function Regressions() {
  const navigate = useNavigate();
  const [severity, setSeverity] = useState<Severity>("all");
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data, isLoading } = useRegressions({
    severity: severity === "all" ? undefined : severity,
    limit,
    offset: page * limit,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 animate-fade-up">
        <div>
          <p className="text-2xs uppercase tracking-widest text-muted font-mono">
            regression feed
          </p>
          <h1 className="font-display text-3xl font-semibold text-primary tracking-tightest mt-1.5 leading-tight">
            Things that got{" "}
            <span className="bg-gradient-to-r from-bad via-warn to-bad bg-clip-text text-transparent">
              slower.
            </span>
          </h1>
          <p className="text-secondary text-sm mt-1.5">
            <span className="num text-primary">{total.toLocaleString()}</span>{" "}
            total · filtered by deterministic rules over consecutive collector runs.
          </p>
        </div>
        <div className="flex gap-1 p-1 bg-panel-2 rounded-md ring-1 ring-edge">
          {SEVERITIES.map((s) => (
            <button
              key={s}
              onClick={() => {
                setSeverity(s);
                setPage(0);
              }}
              className={`px-3 py-1.5 rounded text-2xs font-mono uppercase tracking-widest transition-colors ${
                severity === s
                  ? "bg-ink text-primary ring-1 ring-edge"
                  : "text-muted hover:text-secondary"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <Section icon={AlertTriangle} title="Detections" hint="newest first">
        {isLoading ? (
          <div className="p-5 space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <p className="text-sm text-muted">
              No regressions match this filter.
            </p>
            <p className="text-2xs text-muted mt-2 font-mono">
              try running <span className="text-accent">make demo</span> to seed examples.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-2xs uppercase tracking-widest text-muted">
                  <th className="px-5 py-2.5 font-medium">Severity</th>
                  <th className="px-4 py-2.5 font-medium">Type</th>
                  <th className="px-4 py-2.5 font-medium">Query</th>
                  <th className="px-4 py-2.5 font-medium">Message</th>
                  <th className="px-4 py-2.5 font-medium">Detected</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r, i) => (
                  <tr
                    key={r.id}
                    className={`group cursor-pointer border-t border-edge transition-colors animate-fade-up ${
                      i % 2 === 0 ? "bg-transparent" : "bg-panel-2/30"
                    } hover:bg-accent/5`}
                    style={{ animationDelay: `${Math.min(i * 18, 240)}ms` }}
                    onClick={() => navigate(`/app/queries/${r.fingerprint_id}`)}
                  >
                    <td className="px-5 py-3">
                      <RegressionBadge severity={r.severity} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-2 text-2xs font-mono text-secondary">
                        <RegressionTypeIcon type={r.regression_type} size={12} />
                        {regressionMeta(r.regression_type).label}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-2xs text-primary/90 max-w-xs truncate">
                      {r.normalized_query.slice(0, 80)}
                    </td>
                    <td className="px-4 py-3 text-secondary max-w-sm">
                      {r.message}
                    </td>
                    <td className="px-4 py-3 text-muted text-2xs whitespace-nowrap font-mono">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {total > limit && (
        <div className="flex items-center gap-2 justify-end text-xs text-muted">
          <span className="font-mono">
            {page * limit + 1}–{Math.min((page + 1) * limit, total)} of{" "}
            <span className="num text-secondary">{total}</span>
          </span>
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 surface-2 hover:border-edge-bright disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={12} /> prev
          </button>
          <button
            disabled={(page + 1) * limit >= total}
            onClick={() => setPage((p) => p + 1)}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 surface-2 hover:border-edge-bright disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            next <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
}
