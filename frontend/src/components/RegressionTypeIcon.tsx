import {
  AlertCircle,
  ArrowDownRight,
  ArrowUp,
  CircleDot,
  Database,
  HardDriveDownload,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const TYPE_MAP: Record<string, { Icon: LucideIcon; label: string; tone: string }> = {
  index_scan_to_seq_scan: { Icon: ArrowDownRight, label: "Index → Seq Scan", tone: "text-bad" },
  severe_latency_spike: { Icon: Zap, label: "Severe latency spike", tone: "text-bad" },
  latency_spike: { Icon: TrendingUp, label: "Latency spike", tone: "text-warn" },
  cost_spike: { Icon: ArrowUp, label: "Cost spike", tone: "text-warn" },
  row_estimate_mismatch: { Icon: AlertCircle, label: "Row estimate mismatch", tone: "text-warn" },
  temp_spill: { Icon: HardDriveDownload, label: "Temp spill", tone: "text-warn" },
  call_spike: { Icon: CircleDot, label: "Call spike", tone: "text-secondary" },
  vector_hnsw_index_bypass: { Icon: Database, label: "Vector HNSW bypass", tone: "text-bad" },
};

export function regressionMeta(type: string) {
  return (
    TYPE_MAP[type] || {
      Icon: Database,
      label: type,
      tone: "text-secondary",
    }
  );
}

interface Props {
  type: string;
  size?: number;
  className?: string;
}

export function RegressionTypeIcon({ type, size = 14, className = "" }: Props) {
  const { Icon, tone } = regressionMeta(type);
  return <Icon size={size} className={`${tone} ${className}`} strokeWidth={2} />;
}
