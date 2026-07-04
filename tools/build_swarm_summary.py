"""Index the latest swarm run per scenario into a human-readable summary.

Scans `runs/swarm/` for the most recent run of each SW0–SW3 scenario and emits
`runs/swarm/SWARM_SUMMARY.md` and `SWARM_SUMMARY.csv` with the fleet metrics.

    python -m tools.build_swarm_summary
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

CSV_FIELDS = [
    "scenario_id", "scenario_name", "attack_channel", "victim_breach_rate",
    "number_of_victims_breached", "num_victims", "agents_accepting_poison",
    "time_to_first_breach_s", "time_to_last_breach_s",
    "swarm_propagation_latency_s", "injection_to_first_breach_s",
    "max_fleet_depth_m", "run_folder",
]


def _latest_run(slug: str) -> str | None:
    matches = sorted(glob.glob(os.path.join(config.RUNS_SWARM_DIR, f"{slug}__*")))
    return matches[-1] if matches else None


def collect() -> list[dict]:
    rows = []
    for sid in config.SWARM_SCENARIO_ORDER:
        slug = config.SWARM_SCENARIO_IDS[sid]
        run = _latest_run(slug)
        if not run:
            continue
        cfg = json.load(open(os.path.join(run, config.SWARM_ARTIFACTS["config"])))
        m = json.load(open(os.path.join(run, config.SWARM_ARTIFACTS["metrics"])))["swarm"]
        rows.append({
            "scenario_id": sid,
            "scenario_name": cfg["scenario_name"],
            "attack_channel": cfg.get("attack_channel") or "-",
            "victim_breach_rate": m["victim_breach_rate"],
            "number_of_victims_breached": m["number_of_victims_breached"],
            "num_victims": m["num_victims"],
            "agents_accepting_poison": m["agents_accepting_poison"],
            "time_to_first_breach_s": m["time_to_first_breach_s"],
            "time_to_last_breach_s": m["time_to_last_breach_s"],
            "swarm_propagation_latency_s": m["swarm_propagation_latency_s"],
            "injection_to_first_breach_s": m["injection_to_first_breach_s"],
            "max_fleet_depth_m": m["max_fleet_depth_m"],
            "run_folder": os.path.relpath(run, config.HERE),
        })
    return rows


def write_summary(rows: list[dict]) -> tuple[str, str]:
    csv_path = os.path.join(config.RUNS_SWARM_DIR, "SWARM_SUMMARY.csv")
    md_path = os.path.join(config.RUNS_SWARM_DIR, "SWARM_SUMMARY.md")

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)

    lines = [
        "# Swarm Red-Team Validation Summary (SW0–SW3, sim)",
        "",
        f"- **Benchmark:** {config.BENCHMARK_FULL} — swarm extension (offline sim, no PX4)",
        f"- **Fleet:** attacker `{config.SWARM_ATTACKER}` + victims "
        f"{', '.join(f'`{v}`' for v in config.SWARM_VICTIMS)} "
        f"+ benign `{config.SWARM_COORDINATOR}`",
        f"- **LLM victim model:** {config.LLM_MODEL}",
        f"- **NFZ:** NORTH {config.NFZ['north_min']}–{config.NFZ['north_max']}, "
        f"EAST {config.NFZ['east_min']} to {config.NFZ['east_max']}",
        "",
        "| ID | Scenario | Attack channel | Breach rate | Breached | Accepted poison | "
        "First breach (s) | Last breach (s) | Propagation (s) | Max depth (m) |",
        "|----|----------|----------------|-------------|----------|-----------------|"
        "------------------|-----------------|-----------------|---------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['scenario_id']} | {r['scenario_name']} | {r['attack_channel']} | "
            f"{r['victim_breach_rate']} | {r['number_of_victims_breached']}/{r['num_victims']} | "
            f"{r['agents_accepting_poison']}/{r['num_victims']} | "
            f"{r['time_to_first_breach_s']} | {r['time_to_last_breach_s']} | "
            f"{r['swarm_propagation_latency_s']} | {r['max_fleet_depth_m']} |")
    lines += [
        "",
        "Each run folder holds the full evidence chain: shared memory audit log, "
        "per-agent LLM prompt/response/parsed action, per-agent decision log, "
        "per-agent telemetry CSV, swarm metrics JSON, all-drone trajectory plot, "
        "and a run report. Regenerate with `python -m tools.build_swarm_summary`.",
        "",
        "## Run folders",
        "",
    ]
    for r in rows:
        lines.append(f"- **{r['scenario_id']}** — `{r['run_folder']}`")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return md_path, csv_path


def main() -> None:
    rows = collect()
    if not rows:
        raise SystemExit("no swarm runs found under runs/swarm/")
    md, csvp = write_summary(rows)
    print(f"[swarm-summary] wrote {md}")
    print(f"[swarm-summary] wrote {csvp}")
    for r in rows:
        print(f"  {r['scenario_id']}: {r['number_of_victims_breached']}/{r['num_victims']} "
              f"breached (rate {r['victim_breach_rate']})")


if __name__ == "__main__":
    main()
