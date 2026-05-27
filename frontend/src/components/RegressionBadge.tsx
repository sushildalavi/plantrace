interface Props {
  severity: "critical" | "high" | "medium" | "low";
  className?: string;
}

const styles = {
  critical: { dot: "bg-bad", text: "text-bad", ring: "ring-bad bg-bad/20" },
  high: { dot: "bg-bad", text: "text-bad", ring: "ring-bad/30 bg-bad/10" },
  medium: { dot: "bg-warn", text: "text-warn", ring: "ring-warn/30 bg-warn/10" },
  low: { dot: "bg-secondary", text: "text-secondary", ring: "ring-edge bg-panel-2" },
};

export function RegressionBadge({ severity, className = "" }: Props) {
  const s = styles[severity];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded ring-1 ${s.ring} ${s.text} text-2xs font-mono uppercase tracking-wider ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {severity}
    </span>
  );
}
