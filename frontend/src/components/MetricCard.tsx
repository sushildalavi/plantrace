import type { LucideIcon } from "lucide-react";
import { Spotlight } from "./Spotlight";
import { Ticker } from "./Ticker";

interface Props {
  label: string;
  value: string | number | null | undefined;
  hint?: string;
  tone?: "default" | "warn" | "bad" | "ok";
  icon?: LucideIcon;
  unit?: string;
  decimals?: number;
}

const toneIcon = {
  default: "text-secondary",
  warn: "text-warn",
  bad: "text-bad",
  ok: "text-ok",
};

const glowMap = {
  default: "rgba(78, 161, 255, 0.16)",
  warn: "rgba(251, 191, 36, 0.16)",
  bad: "rgba(251, 113, 133, 0.18)",
  ok: "rgba(45, 212, 191, 0.14)",
};

const accentBar = {
  default: "from-accent/0 via-accent/30 to-accent/0",
  warn: "from-warn/0 via-warn/30 to-warn/0",
  bad: "from-bad/0 via-bad/30 to-bad/0",
  ok: "from-ok/0 via-ok/30 to-ok/0",
};

export function MetricCard({
  label,
  value,
  hint,
  tone = "default",
  icon: Icon,
  unit,
  decimals = 0,
}: Props) {
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string"
      ? Number(value)
      : null;
  const isNum = numeric != null && !isNaN(numeric);

  return (
    <Spotlight
      className="surface group transition-all duration-300 hover:border-edge-bright hover:translate-y-[-1px]"
      glow={glowMap[tone]}
    >
      <div
        className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accentBar[tone]} opacity-60`}
        aria-hidden
      />
      <div className="relative p-4">
        <div className="flex items-center justify-between">
          <span className="text-2xs uppercase tracking-widest text-muted font-medium">
            {label}
          </span>
          {Icon && (
            <span className="grid place-items-center w-6 h-6 rounded bg-panel-2 ring-1 ring-edge transition-colors group-hover:ring-edge-bright">
              <Icon size={12} className={toneIcon[tone]} strokeWidth={2.25} />
            </span>
          )}
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-[28px] font-display font-semibold text-primary tracking-tightest leading-none">
            {value == null ? (
              <span className="text-muted">—</span>
            ) : isNum ? (
              <Ticker value={numeric} decimals={decimals} />
            ) : (
              <span className="num">{value}</span>
            )}
          </span>
          {unit && <span className="text-xs text-muted font-mono">{unit}</span>}
        </div>
        {hint && <p className="mt-1.5 text-2xs text-muted">{hint}</p>}
      </div>
    </Spotlight>
  );
}
