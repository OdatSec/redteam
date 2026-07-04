# Exact PX4/Gazebo run command — S4L (08_llm_stealth_drift_through_nfz)

## Clean restart (before this run)

```bash
pkill -9 -f 'bin/px4'; pkill -9 -f 'gz sim'; pkill -9 -f 'ruby.*gz'; sleep 3
rm -f /tmp/px4_lock-0 /tmp/px4-sock-*
```

## Launch PX4 + Gazebo (GUI visible, gz_x500_depth, NFZ world)

```bash
cd /home/px4/PX4-Autopilot
export DISPLAY=:1
export PX4_GZ_WORLD=nfz_restricted_zone
make px4_sitl gz_x500_depth
```

## Run the scenario (LLM victim, backend=px4)

```bash
cd /home/px4/collaboration/redteam
python run_experiment.py --scenario S4L --backend px4
```

Orchestrated end-to-end (clean restart + launch + run + frame capture) via:

```bash
python -m tools.run_px4_validation --scenario S4L --vehicle gz_x500_depth
```

- LLM model: `qwen2.5:7b`
- Vehicle: `gz_x500_depth` (x500_depth)  ·  World: `nfz_restricted_zone`  ·  GUI: visible (DISPLAY=:1)
- Run folder: `runs/gazebo/08_llm_stealth_drift_through_nfz__20260704_170512`

## Evidence chain in this folder

`03_memory_audit_log.jsonl`, `10_llm_prompt.txt`, `11_llm_raw_response.txt`,
`12_llm_parsed_action.json`, `13_llm_decisions.jsonl`, `04_flight_telemetry.csv`,
`05_breach_metrics.json`, `06_trajectory_map_2d_nfz.png`, `00_run_report.md`,
`gazebo_start_frame.png`, `gazebo_breach_frame.png`.
