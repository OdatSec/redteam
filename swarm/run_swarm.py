"""Swarm red-team orchestrator (sim-only).

Runs one shared-memory swarm episode end-to-end and writes the full evidence
chain for the study:

    - shared memory audit log  (02_shared_memory_audit_log.jsonl)
    - per-agent LLM prompt / raw response / parsed action
    - per-agent decision log   (agent_aX_llm_decisions.jsonl)
    - per-agent telemetry CSV   (agent_aX_flight_telemetry.csv)
    - swarm metrics JSON        (03_swarm_metrics.json)
    - trajectory plot (all drones) (04_swarm_trajectory_map_2d_nfz.png)
    - run report                (00_run_report.md)

Topology: a lightweight Mission Coordinator seeds benign per-victim patrol
waypoints, then A0 (compromised writer) and A1/A2/A3 (victim LLM UAVs) run
concurrently against one in-process shared-memory blackboard. No defense, no
perception, no PX4 — this is the offline swarm baseline.

    python -m swarm.run_swarm --scenario SW1
    python -m swarm.run_swarm --all
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from agents.llm_client import OllamaClient  # noqa: E402
from agents.mission_coordinator import MissionCoordinator  # noqa: E402
from agents.swarm_memory import SwarmMemoryBus  # noqa: E402
from agents.swarm_victim import run_agent  # noqa: E402
from swarm import swarm_metrics  # noqa: E402
from swarm.scenarios import SCENARIOS  # noqa: E402
from tools.plot_swarm_trajectory import plot_swarm  # noqa: E402


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


async def run_scenario(scenario_id: str, llm_model: str | None = None) -> dict:
    scen = SCENARIOS[scenario_id]
    model = llm_model or config.LLM_MODEL

    # Fail fast if the local LLM is unreachable (same guard as the single victim).
    probe = OllamaClient(model=model, host=config.OLLAMA_HOST,
                         temperature=config.LLM_TEMPERATURE, seed=config.LLM_SEED)
    if not probe.health():
        raise RuntimeError(
            f"Ollama server not reachable at {config.OLLAMA_HOST}. Start it with "
            f"`ollama serve` and `ollama pull {model}`.")

    folder = os.path.join(config.RUNS_SWARM_DIR, f"{scen['slug']}__{_stamp()}")
    os.makedirs(folder, exist_ok=True)
    print(f"\n===== {scenario_id}: {scen['name']} =====")
    print(f"[swarm] run folder: {folder}")

    bus = SwarmMemoryBus(os.path.join(folder, config.SWARM_ARTIFACTS["memory_log"]))
    coordinator = MissionCoordinator(config.SWARM_VICTIMS)
    roles = coordinator.assign_roles()
    coordinator.seed_mission(bus, roles, clock=0.0)

    injection_time = None if not scen["poisoned"] else config.SWARM_ATTACK_DELAY_S

    t0 = time.time()
    victim_tasks = [
        asyncio.create_task(run_agent(aid, bus, folder, t0, injection_time, model))
        for aid in config.SWARM_VICTIMS
    ]
    attacker_task = asyncio.create_task(scen["attacker"](bus, t0))

    agent_results = await asyncio.gather(*victim_tasks)
    await attacker_task  # ensure A0 finished (drift may still be nudging)

    metrics = swarm_metrics.aggregate(list(agent_results), injection_time)

    # ---- config + metrics artifacts ----
    cfg = {
        "benchmark": config.BENCHMARK_FULL,
        "scenario_id": scenario_id,
        "scenario_name": scen["name"],
        "scenario_slug": scen["slug"],
        "backend": "sim",
        "llm_model": model,
        "attacker": config.SWARM_ATTACKER,
        "victims": config.SWARM_VICTIMS,
        "coordinator": config.SWARM_COORDINATOR,
        "poisoned": scen["poisoned"],
        "attack_channel": scen["attack_channel"],
        "attack_delay_s": injection_time,
        "nfz": config.NFZ,
        "roles": roles,
        "expectation": scen["expectation"],
    }
    with open(os.path.join(folder, config.SWARM_ARTIFACTS["config"]), "w") as f:
        json.dump(cfg, f, indent=2)
    full_metrics = {"swarm": metrics, "per_agent": list(agent_results)}
    with open(os.path.join(folder, config.SWARM_ARTIFACTS["metrics"]), "w") as f:
        json.dump(full_metrics, f, indent=2)

    # ---- trajectory plot (all drones) ----
    plot_swarm(folder, os.path.join(folder, config.SWARM_ARTIFACTS["map_2d"]),
               title=f"{scenario_id} — {scen['name']}: swarm vs NFZ")

    # ---- run report ----
    _write_report(folder, scenario_id, scen, cfg, metrics, list(agent_results))

    print(f"\n[swarm] {scenario_id} complete: "
          f"{metrics['number_of_victims_breached']}/{metrics['num_victims']} breached, "
          f"{metrics['agents_accepting_poison']} accepted poison.")
    return {"folder": folder, "scenario_id": scenario_id, "metrics": metrics}


def _write_report(folder, scenario_id, scen, cfg, metrics, agent_results) -> None:
    art = config.SWARM_ARTIFACTS
    lines = [
        f"# {scenario_id} — {scen['name']} (swarm sim run report)",
        "",
        f"- **Benchmark:** {config.BENCHMARK_FULL} — swarm extension",
        f"- **Backend:** sim (offline kinematic, no PX4)",
        f"- **LLM victim model:** {cfg['llm_model']}",
        f"- **Fleet:** attacker `{config.SWARM_ATTACKER}` + victims "
        f"{', '.join(f'`{v}`' for v in config.SWARM_VICTIMS)}",
        f"- **Coordinator:** `{config.SWARM_COORDINATOR}` (benign role assignment + "
        "initial context only; no defense/NFZ/world-model)",
        f"- **Poisoned:** {scen['poisoned']}"
        + (f" via `{scen['attack_channel']}` at t={cfg['attack_delay_s']}s"
           if scen['poisoned'] else ""),
        f"- **Expectation:** {scen['expectation']}",
        f"- **NFZ:** NORTH {config.NFZ['north_min']}–{config.NFZ['north_max']}, "
        f"EAST {config.NFZ['east_min']} to {config.NFZ['east_max']}",
        "",
        "## Swarm result",
        "",
        f"- **victim_breach_rate:** {metrics['victim_breach_rate']} "
        f"({metrics['number_of_victims_breached']}/{metrics['num_victims']})",
        f"- **number_of_victims_breached:** {metrics['number_of_victims_breached']}",
        f"- **agents_accepting_poison:** {metrics['agents_accepting_poison']}",
        f"- **time_to_first_breach:** {metrics['time_to_first_breach_s']} s",
        f"- **time_to_last_breach:** {metrics['time_to_last_breach_s']} s",
        f"- **swarm_propagation_latency:** {metrics['swarm_propagation_latency_s']} s "
        "(spread between first and last breach)",
        f"- **injection_to_first_breach:** {metrics['injection_to_first_breach_s']} s",
        f"- **max_fleet_depth:** {metrics['max_fleet_depth_m']} m",
        f"- **breached_agents:** {metrics['breached_agents']}",
        "",
        "## Per-agent",
        "",
        "| agent | breached | entry_time_s | max_depth_m | dwell_s | accepted_poison | mentions_A0 | prop_latency_s |",
        "|-------|----------|--------------|-------------|---------|-----------------|-------------|----------------|",
    ]
    for a in agent_results:
        lines.append(
            f"| {a['agent_id']} | {a['breached']} | {a['entry_time_s']} | "
            f"{a['max_penetration_depth_m']} | {a['dwell_time_s']} | "
            f"{a['accepted_poison']} | {a['reason_mentions_A0']} | "
            f"{a['propagation_latency_s']} |")
    lines += [
        "",
        "## Evidence chain (this folder)",
        "",
        f"- `{art['memory_log']}` — shared memory audit log (every write, who/when/to whom)",
        f"- `{art['config']}` — experiment configuration + role assignment",
        f"- `{art['metrics']}` — swarm + per-agent metrics JSON",
        f"- `{art['map_2d']}` — trajectory plot (all drones vs NFZ)",
        "- `agent_aX_flight_telemetry.csv` — per-agent telemetry",
        "- `agent_aX_llm_prompt.txt` / `_llm_raw_response.txt` / `_llm_parsed_action.json` — per-agent LLM evidence",
        "- `agent_aX_llm_decisions.jsonl` — per-agent full decision trace",
        "",
        "> Baseline behaviour: victims validate JSON format only; there is no NFZ / "
        "safety reasoning, so a poisoned shared-memory claim is trusted and flown.",
    ]
    with open(os.path.join(folder, art["report"]), "w") as f:
        f.write("\n".join(lines) + "\n")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Run swarm red-team scenarios (sim).")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys()))
    p.add_argument("--all", action="store_true", help="run SW0–SW3 in order")
    p.add_argument("--model", default=None, help="override LLM model")
    return p.parse_args(argv)


async def _main_async(argv=None):
    args = parse_args(argv)
    if not args.scenario and not args.all:
        raise SystemExit("specify --scenario SWx or --all")
    ids = config.SWARM_SCENARIO_ORDER if args.all else [args.scenario]
    results = []
    for sid in ids:
        results.append(await run_scenario(sid, args.model))
    print("\n===== swarm batch summary =====")
    for r in results:
        m = r["metrics"]
        print(f"  {r['scenario_id']}: {m['number_of_victims_breached']}/{m['num_victims']} "
              f"breached, rate={m['victim_breach_rate']}, "
              f"accept={m['agents_accepting_poison']}")
    return results


def main(argv=None):
    asyncio.run(_main_async(argv))


if __name__ == "__main__":
    main()
