from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.placement import simulate_placement  # noqa: E402


SCENARIOS = [
    {"seed": 7, "tenants": 24, "regions": 2, "clusters_per_region": 2, "nodes_per_cluster": 2},
    {"seed": 11, "tenants": 36, "regions": 3, "clusters_per_region": 2, "nodes_per_cluster": 3},
    {"seed": 42, "tenants": 48, "regions": 3, "clusters_per_region": 2, "nodes_per_cluster": 3},
    {"seed": 99, "tenants": 72, "regions": 4, "clusters_per_region": 3, "nodes_per_cluster": 3},
]


def _evaluate_scenario(params: dict[str, int]) -> dict[str, Any]:
    result = simulate_placement(**params)
    algorithms = result["algorithms"]
    ordered = sorted(
        algorithms,
        key=lambda algo: (
            algo["comparison"]["balance_after"],
            algo["comparison"]["overloaded_nodes_after"],
            algo["comparison"]["migration_cost"],
        ),
    )
    best = ordered[0]
    return {
        "scenario": params,
        "algorithm_count": len(algorithms),
        "best_algorithm": best["algorithm"],
        "best_comparison": best["comparison"],
        "best_balance": best["comparison"]["balance_after"],
        "best_hotspot_reduction": best["comparison"]["hotspot_reduction"],
        "best_overloaded_reduction": best["comparison"]["overloaded_nodes_before"] - best["comparison"]["overloaded_nodes_after"],
        "best_migration_cost": best["comparison"]["migration_cost"],
        "algorithms": algorithms,
        "telemetry_rows": len(result["telemetry"]),
    }


def evaluate() -> dict[str, Any]:
    rows = [_evaluate_scenario(s) for s in SCENARIOS]

    balance_improvements = [
        scenario["best_comparison"]["balance_before"] - scenario["best_comparison"]["balance_after"]
        for scenario in rows
    ]
    hotspot_reductions = [
        scenario["best_comparison"]["hotspot_reduction"]
        for scenario in rows
    ]
    overloaded_reductions = [
        scenario["best_comparison"]["overloaded_nodes_before"] - scenario["best_comparison"]["overloaded_nodes_after"]
        for scenario in rows
    ]
    score_improvements = [
        scenario["best_comparison"]["placement_score_after"] - scenario["best_comparison"]["placement_score_before"]
        for scenario in rows
    ]
    headroom_improvements = [
        scenario["best_comparison"]["capacity_headroom_after"] - scenario["best_comparison"]["capacity_headroom_before"]
        for scenario in rows
    ]

    return {
        "generated_at": "synthetic-local",
        "scenarios": len(rows),
        "algorithms": 5,
        "best_balance_improvement": round(mean(balance_improvements), 6),
        "best_hotspot_reduction": round(mean(hotspot_reductions), 6),
        "best_overloaded_reduction": round(mean(overloaded_reductions), 6),
        "best_score_improvement": round(mean(score_improvements), 6),
        "best_headroom_improvement": round(mean(headroom_improvements), 6),
        "rows": rows,
    }


def main() -> None:
    out_dir = ROOT / "backend" / "benchmark_results"
    out_dir.mkdir(exist_ok=True)
    summary = evaluate()
    json_path = out_dir / "placement_eval.json"
    csv_path = out_dir / "placement_eval.csv"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="") as f:
        fieldnames = [
            "scenario_seed",
            "scenario_tenants",
            "scenario_regions",
            "telemetry_rows",
            "best_algorithm",
            "best_balance",
            "best_hotspot_reduction",
            "best_overloaded_reduction",
            "best_migration_cost",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["rows"]:
            scenario = row["scenario"]
            writer.writerow(
                {
                    "scenario_seed": scenario["seed"],
                    "scenario_tenants": scenario["tenants"],
                    "scenario_regions": scenario["regions"],
                    "telemetry_rows": row["telemetry_rows"],
                    "best_algorithm": row["best_algorithm"],
                    "best_balance": row["best_balance"],
                    "best_hotspot_reduction": row["best_hotspot_reduction"],
                    "best_overloaded_reduction": row["best_overloaded_reduction"],
                    "best_migration_cost": row["best_migration_cost"],
                }
            )

        scenario_dir = out_dir / "placement_scenarios"
        scenario_dir.mkdir(exist_ok=True)
        for row in summary["rows"]:
            scenario_name = f"scenario_seed_{row['scenario']['seed']}"
            (scenario_dir / f"{scenario_name}.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
