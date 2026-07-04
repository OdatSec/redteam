# Offline simulator results

Python kinematic simulator — **no PX4, no Gazebo**.

Fast, reproducible benchmark for all 5 attack scenarios.

```bash
python run_experiment.py --all --backend sim
```

Each run folder: `00_run_report.md` → maps & metrics inside.

Compare with real flight: [`../gazebo/`](../gazebo/)
