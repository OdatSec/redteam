# Run folders & file names — quick guide

**Benchmark:** RedTeam v0.1 — see [`REDTEAM_METHODOLOGY.md`](../REDTEAM_METHODOLOGY.md)

Results are in **two separate folders**:

```text
redteam/runs/
├── sim/          offline Python simulator (--backend sim)
└── gazebo/       real PX4 + Gazebo + MAVSDK (--backend px4)
```

---

## Scenario IDs (S0–S4)

| ID | Slug | CLI alias | Attack |
|----|------|-----------|--------|
| **S0** | `01_clean_mission` | `clean` | none (control) |
| **S1** | `02_static_poison_inside_nfz` | `static_inside` | poison before flight → N=8 |
| **S2** | `03_runtime_poison_inside_nfz` | `runtime_inside` | poison at t=8s → N=8 |
| **S3** | `04_runtime_poison_behind_nfz` | `runtime_behind` | poison at t=8s → N=15 ★ |
| **S4** | `05_stealth_drift_through_nfz` | `stealth_drift` | gradual nudges → N=15 |

---

## Files inside each run (numbered)

| File | sim | gazebo | What it is |
|------|:---:|:------:|------------|
| `00_run_report.md` | ✓ | ✓ | Start here |
| `01_experiment_config.json` | ✓ | ✓ | NFZ, targets, timing |
| `02_final_poisoned_memory.json` | ✓ | ✓ | Last poisoned command |
| `03_memory_audit_log.jsonl` | ✓ | ✓ | Memory audit trail |
| `04_flight_telemetry.csv` | ✓ | ✓ | Position every tick |
| `05_breach_metrics.json` | ✓ | ✓ | Breach scores |
| `06_trajectory_map_2d_nfz.png` | ✓ | ✓ | 2D red NFZ map |
| `07_attack_replay_2d_animation.mp4` | ✓ | ✓ | 2D animated replay |
| `08_gazebo_flight_recording_3d.mp4` | — | ✓ | Gazebo screen capture |
| `09_gazebo_and_map_split_screen.mp4` | — | ✓ | Gazebo + map side-by-side |

---

## Commands

```bash
# Offline — saves to runs/sim/
python run_experiment.py --all --backend sim

# Real flight — saves to runs/gazebo/
python run_experiment.py --scenario runtime_behind --backend px4
```

Visualizations: [`VISUALIZATION.md`](VISUALIZATION.md)
