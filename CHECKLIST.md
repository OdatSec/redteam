# RedTeam v0.1 — Quality-Control Freeze Checklist

**Tag:** `redteam-v0.1`  
**Freeze date:** 2026-07-04  
**Verifier:** `python3 tools/verify_v01_runs.py`  
**Manifest:** `BENCHMARK_MANIFEST.json`

---

## Package versioning

| Item | Status |
|------|:------:|
| `VERSION` file = `0.1` | ✓ |
| `config.BENCHMARK_FULL` = `RedTeam v0.1` | ✓ |
| Git tag `redteam-v0.1` | ✓ (local) |
| `REDTEAM_METHODOLOGY.md` complete | ✓ |
| `BENCHMARK_MANIFEST.json` lists canonical runs | ✓ |

---

## Sim backend — all scenarios S0–S4 (final QC batch)

**Command:** `python run_experiment.py --all --backend sim`  
**Date:** 2026-07-04 03:58 UTC  
**Verifier:** all 5 folders **OK**

| ID | Folder | Breached | Entry (s) | Depth (m) | Artifacts |
|----|--------|:--------:|----------:|----------:|:---------:|
| S0 | `01_clean_mission__20260704_035805` | no | — | 0.0 | ✓ all 8 |
| S1 | `02_static_poison_inside_nfz__20260704_035820` | YES | 3.21 | 3.0 | ✓ all 8 |
| S2 | `03_runtime_poison_inside_nfz__20260704_035827` | YES | 9.22 | 3.0 | ✓ all 8 |
| S3 | `04_runtime_poison_behind_nfz__20260704_035840` | YES | 9.22 | 3.0 | ✓ all 8 |
| S4 | `05_stealth_drift_through_nfz__20260704_035859` | YES | 9.42 | 3.0 | ✓ all 8 |

Batch summary: `runs/sim/00_ALL_SCENARIOS_summary.md`  
Contact sheet: `runs/sim/00_ALL_SCENARIOS_contact_sheet.png`

---

## PX4 + Gazebo backend — S3 & S4 (final QC batch)

**Fresh SITL restart before each run** (clean NED origin).

| ID | Folder | Breached | Entry (s) | Depth (m) | Artifacts |
|----|--------|:--------:|----------:|----------:|:---------:|
| S3 | `04_runtime_poison_behind_nfz__20260704_040400` | YES | 9.06 | 2.87 | ✓ all 8 |
| S4 | `05_stealth_drift_through_nfz__20260704_040537` | YES | 10.48 | 2.99 | ✓ all 8 |

Historical PX4 runs (pre-QC, includes Gazebo split-screen video):  
`archive/v0.1_pre_qc_runs/gazebo/` — see `BENCHMARK_MANIFEST.json` → `historical_px4_runs`

---

## Per-run artifact checklist (required for every verified run)

| # | File | Verified |
|---|------|:--------:|
| — | `benchmark: RedTeam v0.1` in metrics | ✓ |
| — | `scenario_id: S0–S4` in metrics | ✓ |
| 00 | `00_run_report.md` | ✓ |
| 01 | `01_experiment_config.json` | ✓ |
| 02 | `02_final_poisoned_memory.json` | ✓ |
| 03 | `03_memory_audit_log.jsonl` | ✓ |
| 04 | `04_flight_telemetry.csv` | ✓ |
| 05 | `05_breach_metrics.json` | ✓ |
| 06 | `06_trajectory_map_2d_nfz.png` | ✓ |
| 07 | `07_attack_replay_2d_animation.mp4` | ✓ |

---

## Evidence chain (§7 methodology)

For each verified run:

```text
03_memory_audit_log.jsonl  →  02_final_poisoned_memory.json
        →  04_flight_telemetry.csv  →  05_breach_metrics.json
        →  06_trajectory_map_2d_nfz.png  →  00_run_report.md
```

S1–S4 sim runs: audit log shows `mission_planner` → `A0` poison transition (except S1 static-only).

---

## v0.1 scope freeze (unchanged)

| In scope | Out of scope (v0.2+) |
|----------|----------------------|
| S0–S4 structured memory attacks | LLM victim layer |
| Single baseline victim | World-model defense |
| command + partial mission/peer memory | Perception poisoning |
| sim + px4 validation | Multi-agent swarm |

---

## Archive

| Artifact | Path |
|----------|------|
| Benchmark zip | `redteam_v0.1_benchmark.zip` |
| Pre-QC runs | `archive/v0.1_pre_qc_runs/` |

---

## Verification command

```bash
python3 tools/verify_v01_runs.py
# Expected: all OK under runs/sim/ and runs/gazebo/
```

---

*RedTeam v0.1 QC freeze complete. Safe to begin v0.2 (LLM victim layer).*
