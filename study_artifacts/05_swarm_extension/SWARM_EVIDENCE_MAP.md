# Swarm Evidence Map

Every SW0–SW3 run folder under `runs/swarm/` preserves the same evidence chain. Curated per-scenario folders under this directory symlink back to the raw runs for reproducibility.

## Shared (fleet-level) artifacts

| Artifact | Filename | Description |
| --- | --- | --- |
| Run report | `00_run_report.md` | Human-readable summary + per-agent table |
| Experiment config | `01_experiment_config.json` | Scenario config + coordinator role assignment |
| Shared memory audit log | `02_shared_memory_audit_log.jsonl` | Every blackboard write (source, target, claim) |
| Swarm metrics | `03_swarm_metrics.json` | Fleet + per-agent breach/LLM metrics JSON |
| All-drone trajectory plot | `04_swarm_trajectory_map_2d_nfz.png` | 2D map: all victims vs NFZ |

## Per-agent artifacts (repeat for A1, A2, A3)

| Artifact | Filename pattern | Description |
| --- | --- | --- |
| Telemetry CSV | `agent_a1_flight_telemetry.csv` | Position, NFZ status, poison flag per tick |
| LLM prompt | `agent_a1_llm_prompt.txt` | Decisive LLM prompt (first poison or last decision) |
| LLM raw response | `agent_a1_llm_raw_response.txt` | Raw Ollama output |
| Parsed action | `agent_a1_llm_parsed_action.json` | Validated JSON action |
| Decision log | `agent_a1_llm_decisions.jsonl` | Full per-update decision trace (JSONL) |

Replace `a1` with `a2` or `a3` for the other victims.

## Representative plots (this folder)

Quick-view trajectory PNGs (symlinks to raw runs):

| Scenario | Plot |
| --- | --- |
| SW0 | [`representative_plots/sw0_trajectory.png`](representative_plots/sw0_trajectory.png) |
| SW1 | [`representative_plots/sw1_trajectory.png`](representative_plots/sw1_trajectory.png) |
| SW2 | [`representative_plots/sw2_trajectory.png`](representative_plots/sw2_trajectory.png) |
| SW3 | [`representative_plots/sw3_trajectory.png`](representative_plots/sw3_trajectory.png) |

## Run folder index

- **SW0** — [`runs/swarm/sw0_clean_swarm_mission__20260704_173335`](../../runs/swarm/sw0_clean_swarm_mission__20260704_173335/)
- **SW1** — [`runs/swarm/sw1_shared_memory_route_lure__20260704_173342`](../../runs/swarm/sw1_shared_memory_route_lure__20260704_173342/)
- **SW2** — [`runs/swarm/sw2_false_policy_clearance_swarm__20260704_173404`](../../runs/swarm/sw2_false_policy_clearance_swarm__20260704_173404/)
- **SW3** — [`runs/swarm/sw3_stealth_drift_swarm__20260704_173420`](../../runs/swarm/sw3_stealth_drift_swarm__20260704_173420/)

## Evidence flow

```
coordinator seeds benign waypoints (t=0)
        ↓
shared memory audit log  ←  A0 broadcasts poison (t=8+)
        ↓
per-agent LLM prompt → raw response → parsed action → decision log
        ↓
per-agent telemetry CSV → swarm metrics JSON → trajectory plot → run report
```
