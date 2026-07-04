# RedTeam v0.1 — Memory-Poisoning Benchmark for LLM-UAV Agents

**Scientific benchmark specification:** [`REDTEAM_METHODOLOGY.md`](REDTEAM_METHODOLOGY.md)  
**Run folders:** [`RUNS_GUIDE.md`](RUNS_GUIDE.md) · **Visuals:** [`VISUALIZATION.md`](VISUALIZATION.md)

Attack the **agent brain**, not PX4: poison shared memory → baseline agent executes → NFZ breach.

## Benchmark scenarios (S0–S4)

| ID | Scenario | CLI alias |
|----|----------|-----------|
| S0 | clean mission | `clean` |
| S1 | static poison inside NFZ | `static_inside` |
| S2 | runtime poison inside NFZ | `runtime_inside` |
| S3 | runtime poison behind NFZ | `runtime_behind` |
| S4 | stealth drift through NFZ | `stealth_drift` |

## Quick start

```bash
pip install -r requirements.txt
python run_experiment.py --all --backend sim      # → runs/sim/
python run_experiment.py --scenario S3 --backend px4   # → runs/gazebo/
```

## Repository layout

```
redteam/
├── REDTEAM_METHODOLOGY.md     ← benchmark spec (start here for papers)
├── VERSION                    ← 0.1
├── config.py                  ← NFZ, scenarios, memory types, artifact names
├── run_experiment.py          ← orchestrator
├── agents/                    ← victim + memory bus + backends
├── attacks/                   ← A0 poison launcher
├── world_model/               ← NFZ breach measurement (not defense)
├── tools/                     ← maps, animations, split-screen
├── gazebo/worlds/             ← 3D NFZ world for Gazebo
└── runs/
    ├── sim/                   ← offline simulator results
    └── gazebo/                ← PX4 + Gazebo results
```

## v0.1 scope (frozen)

| In scope | Out of scope |
|----------|--------------|
| S0–S4 memory-poisoning scenarios | LLM reasoning layer |
| Single-agent baseline victim | World-model defense |
| command + partial mission/peer memory | Perception poisoning |
| sim + px4 backends | Multi-agent swarm |

See professor's defense: `../drone-world-model-main/`
