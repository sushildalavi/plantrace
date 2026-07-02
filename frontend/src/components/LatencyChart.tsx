import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Point = Record<string, any>;

interface Props {
  points: Point[];
  dataKey: string;
  label?: string;
  color?: string;
  height?: number;
  unit?: string;
}

export function LatencyChart({
  points,
  dataKey,
  label,
  color = "#4ea1ff",
  height = 180,
  unit = "",
}: Props) {
  if (!points.length) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1.5 text-sm text-muted border border-dashed border-edge rounded-md"
        style={{ height }}
      >
        <span className="font-mono text-2xs uppercase tracking-widest">no data</span>
        <span className="text-xs">run the collector to populate</span>
      </div>
    );
  }

  const formatted = points.map((p) => ({
    ...p,
    t: new Date(p.captured_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));

  // peak point — for a subtle highlight ring
  const peakIdx = formatted.reduce(
    (acc, p, i) => {
      const v = (p as unknown as Record<string, number>)[dataKey];
      const a = (formatted[acc] as unknown as Record<string, number>)[dataKey];
      return v > a ? i : acc;
    },
    0
  );
  const peak = formatted[peakIdx] as unknown as Record<string, number | string>;

  const gradId = `g-${dataKey}-${color.replace(/[^a-z0-9]/gi, "")}`;

  return (
    <div>
      {label && (
        <p className="text-2xs uppercase tracking-widest text-muted font-medium mb-2">
          {label}
        </p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart
          data={formatted}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="#1d314b"
            strokeDasharray="2 4"
            vertical={false}
          />
          <XAxis
            dataKey="t"
            tick={{ fill: "#7f97b5", fontSize: 10, fontFamily: "IBM Plex Mono" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "#7f97b5", fontSize: 10, fontFamily: "IBM Plex Mono" }}
            axisLine={false}
            tickLine={false}
            width={36}
            tickFormatter={(v) => (typeof v === "number" ? v.toFixed(0) : v)}
          />
          <Tooltip
            cursor={{
              stroke: color,
              strokeOpacity: 0.5,
              strokeDasharray: "3 3",
              strokeWidth: 1,
            }}
            contentStyle={{
              background: "#091424",
              border: "1px solid #213654",
              borderRadius: 6,
              fontSize: 12,
              padding: "8px 10px",
              boxShadow: "0 10px 34px rgba(0,0,0,0.36)",
            }}
            labelStyle={{
              color: "#9eb3d1",
              fontSize: 10,
              marginBottom: 4,
              fontFamily: "IBM Plex Mono",
            }}
            itemStyle={{ color: "#eaf2ff", fontFamily: "IBM Plex Mono" }}
            formatter={(v: number | string) =>
              typeof v === "number"
                ? [v.toFixed(2) + (unit ? " " + unit : ""), label || dataKey]
                : [v, label || dataKey]
            }
          />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={1.75}
            fill={`url(#${gradId})`}
            dot={false}
            activeDot={{
              r: 4,
              stroke: color,
              strokeWidth: 2,
              fill: "#091424",
            }}
            isAnimationActive
            animationDuration={700}
            animationEasing="ease-out"
          />
          {formatted.length > 2 && peak && (
            <ReferenceDot
              x={peak.t as string}
              y={peak[dataKey] as number}
              r={3.5}
              stroke={color}
              strokeWidth={2}
              fill="#091424"
              ifOverflow="extendDomain"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
