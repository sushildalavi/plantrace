import { useMemo, useState } from "react";
import { Play, RotateCw, SlidersHorizontal, Sparkles, Table2 } from "lucide-react";
import { usePlacementSimulation } from "../api/hooks";
import { MetricCard } from "../components/MetricCard";
import { Section, Skeleton } from "../components/Section";
import type { PlacementAlgorithm, PlacementNode, PlacementSimulation } from "../types";

const DEFAULTS = {
  seed: 42,
  tenants: 48,
  regions: 3,
  clusters_per_region: 2,
  nodes_per_cluster: 3,
};

function UtilBar({ node }: { node: PlacementNode }) {
  const pct = Math.min(100, Math.round(node.overload_score > 0 ? 100 : node.used.cpu / node.capacity.cpu * 100));
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-2xs font-mono text-muted">
        <span>{node.node_id}</span>
        <span>{node.overloaded ? "overloaded" : "healthy"}</span>
      </div>
      <div className="h-1.5 rounded bg-panel-2 overflow-hidden">
        <div
          className={`h-full ${node.overloaded ? "bg-bad" : "bg-ok"}`}
          style={{ width: `${Math.max(5, pct)}%` }}
        />
      </div>
      <div className="grid grid-cols-4 gap-2 text-2xs text-muted font-mono">
        <span>cpu {node.used.cpu.toFixed(1)}/{node.capacity.cpu.toFixed(1)}</span>
        <span>mem {node.used.memory.toFixed(1)}/{node.capacity.memory.toFixed(1)}</span>
        <span>iops {node.used.iops.toFixed(0)}/{node.capacity.iops.toFixed(0)}</span>
        <span>{node.tenants.length} tenants</span>
      </div>
    </div>
  );
}

function AlgorithmPanel({ algo }: { algo: PlacementAlgorithm }) {
  const hotNodes = algo.nodes.slice().sort((a, b) => b.overload_score - a.overload_score);
  return (
    <Section
      icon={Table2}
      title={algo.algorithm}
      hint={`balance ${algo.comparison.balance_after.toFixed(4)} · hotspot reduction ${algo.comparison.hotspot_reduction.toFixed(2)}`}
    >
      <div className="p-5 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="surface-2 p-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">overloaded</p>
            <p className="mt-1 text-lg font-semibold text-primary num">
              {algo.comparison.overloaded_nodes_after}
            </p>
          </div>
          <div className="surface-2 p-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">balance</p>
            <p className="mt-1 text-lg font-semibold text-primary num">
              {algo.comparison.balance_after.toFixed(4)}
            </p>
          </div>
          <div className="surface-2 p-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">migration cost</p>
            <p className="mt-1 text-lg font-semibold text-primary num">
              {algo.comparison.migration_cost.toFixed(2)}
            </p>
          </div>
          <div className="surface-2 p-3">
            <p className="text-2xs uppercase tracking-widest text-muted font-mono">decision p95</p>
            <p className="mt-1 text-lg font-semibold text-primary num">
              {algo.comparison.p95_decision_latency_ms.toFixed(2)}ms
            </p>
          </div>
        </div>
        <div className="space-y-3">
          {hotNodes.map((node) => (
            <UtilBar key={node.node_id} node={node} />
          ))}
        </div>
      </div>
    </Section>
  );
}

export function PlacementSimulator() {
  const [request, setRequest] = useState(DEFAULTS);
  const simulationMutation = usePlacementSimulation();
  const [result, setResult] = useState<PlacementSimulation | null>(null);

  const selectedAlgorithms = useMemo(
    () => result?.algorithms ?? [],
    [result]
  );
  const baselineAlgorithm = selectedAlgorithms.find((algo) => algo.algorithm === "first-fit") ?? selectedAlgorithms[0];
  const optimizedAlgorithm = useMemo(() => {
    return selectedAlgorithms
      .slice()
      .sort((a, b) => a.comparison.balance_after - b.comparison.balance_after || a.comparison.overloaded_nodes_after - b.comparison.overloaded_nodes_after)[0];
  }, [selectedAlgorithms]);

  const handleRun = async () => {
    const out = await simulationMutation.mutateAsync(request);
    setResult(out);
  };

  const algoSummary = result?.algorithms ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between animate-fade-up">
        <div>
          <p className="text-2xs uppercase tracking-widest text-muted font-mono">
            placement simulator
          </p>
          <h1 className="font-display text-3xl sm:text-4xl font-semibold text-primary tracking-tightest mt-1.5 leading-[1.05]">
            Synthetic multi-tenant
            <br className="sm:hidden" />{" "}
            <span className="bg-gradient-to-r from-accent via-accent-soft to-accent bg-clip-text text-transparent">
              placement optimization.
            </span>
          </h1>
          <p className="mt-2 text-sm text-secondary max-w-2xl leading-relaxed">
            What-if placement runs over synthetic tenant telemetry. Compare first-fit,
            greedy best-fit, weighted scoring, and a local-search rebalancer across
            overloaded nodes, balance, migration cost, hotspot reduction, and decision latency.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={simulationMutation.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent text-ink font-medium text-sm hover:bg-accent-soft transition-colors disabled:opacity-60"
        >
          {simulationMutation.isPending ? (
            <RotateCw size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          {simulationMutation.isPending ? "Simulating…" : "Run simulation"}
        </button>
      </div>

      <Section icon={SlidersHorizontal} title="Scenario" hint="synthetic tenant telemetry">
        <div className="p-5 grid md:grid-cols-5 gap-3">
          {(
            [
              ["seed", "Seed"],
              ["tenants", "Tenants"],
              ["regions", "Regions"],
              ["clusters_per_region", "Clusters / region"],
              ["nodes_per_cluster", "Nodes / cluster"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="space-y-1">
              <span className="text-2xs uppercase tracking-widest text-muted font-mono">{label}</span>
              <input
                type="number"
                value={request[key]}
                onChange={(e) => setRequest((curr) => ({ ...curr, [key]: Number(e.target.value) }))}
                className="w-full rounded-md border border-edge bg-panel-2 px-3 py-2 text-sm text-primary outline-none focus:ring-1 focus:ring-accent/50"
              />
            </label>
          ))}
        </div>
      </Section>

      {simulationMutation.isPending && <Skeleton className="h-32 w-full" />}

      {result && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 stagger-fast">
            <MetricCard label="Telemetry rows" value={result.telemetry.length} icon={Sparkles} hint="synthetic multi-tenant signals" />
            <MetricCard label="Algorithms" value={result.algorithms.length} icon={Table2} hint="comparison strategies" />
            <MetricCard label="Regions" value={result.regions} icon={SlidersHorizontal} hint="placement topology" />
            <MetricCard label="Tenants" value={result.tenants} icon={Sparkles} hint="workloads in simulation" />
          </div>

          <Section icon={Table2} title="Algorithm comparison" hint="lower balance and overloaded-node counts are better">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-2xs uppercase tracking-widest text-muted">
                    <th className="px-5 py-2.5 font-medium">Algorithm</th>
                    <th className="px-4 py-2.5 font-medium">Overloaded</th>
                    <th className="px-4 py-2.5 font-medium">Balance</th>
                    <th className="px-4 py-2.5 font-medium">Migration</th>
                    <th className="px-4 py-2.5 font-medium">Hotspot reduction</th>
                    <th className="px-4 py-2.5 font-medium">Decision p95</th>
                  </tr>
                </thead>
                <tbody>
                  {algoSummary.map((algo) => (
                    <tr key={algo.algorithm} className="border-t border-edge">
                      <td className="px-5 py-3 font-mono text-xs text-primary">{algo.algorithm}</td>
                      <td className="px-4 py-3 text-secondary num">{algo.comparison.overloaded_nodes_after}</td>
                      <td className="px-4 py-3 text-secondary num">{algo.comparison.balance_after.toFixed(4)}</td>
                      <td className="px-4 py-3 text-secondary num">{algo.comparison.migration_cost.toFixed(2)}</td>
                      <td className="px-4 py-3 text-secondary num">{algo.comparison.hotspot_reduction.toFixed(2)}</td>
                      <td className="px-4 py-3 text-secondary num">{algo.comparison.p95_decision_latency_ms.toFixed(2)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {baselineAlgorithm && optimizedAlgorithm && (
            <Section icon={Sparkles} title="Before / after utilization" hint="baseline first-fit versus the best-balanced strategy">
              <div className="grid lg:grid-cols-2 gap-4 p-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-primary">Before: {baselineAlgorithm.algorithm}</h3>
                    <span className="text-2xs font-mono text-muted">balance {baselineAlgorithm.comparison.balance_after.toFixed(4)}</span>
                  </div>
                  {baselineAlgorithm.nodes.slice(0, 5).map((node) => (
                    <UtilBar key={node.node_id} node={node} />
                  ))}
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-primary">After: {optimizedAlgorithm.algorithm}</h3>
                    <span className="text-2xs font-mono text-muted">balance {optimizedAlgorithm.comparison.balance_after.toFixed(4)}</span>
                  </div>
                  {optimizedAlgorithm.nodes.slice(0, 5).map((node) => (
                    <UtilBar key={node.node_id} node={node} />
                  ))}
                </div>
              </div>
            </Section>
          )}

          {selectedAlgorithms.map((algo) => (
            <AlgorithmPanel key={algo.algorithm} algo={algo} />
          ))}
        </>
      )}
    </div>
  );
}
