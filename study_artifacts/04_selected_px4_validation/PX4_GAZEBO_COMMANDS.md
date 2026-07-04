# PX4 / Gazebo commands & workflow (Phase 4)

Exact, verified commands for validating selected LLM memory-poisoning scenarios
against **PX4 SITL + Gazebo** with the **`x500_depth`** vehicle and the NFZ world.

- Vehicle: **`x500_depth`** (PX4 target `gz_x500_depth`)
- World: **`nfz_restricted_zone`** (red transparent NFZ prism; NORTH 5–12, EAST −3 to 3)
- GUI: **visible, not headless** (`DISPLAY=:1`)
- LLM: `qwen2.5:7b` (Ollama, local)

Paths:
- PX4: `/home/px4/PX4-Autopilot`
- Red-team repo: `/home/px4/collaboration/redteam`
- World source: `redteam/gazebo/worlds/nfz_restricted_zone.sdf`
  (symlinked into `PX4-Autopilot/Tools/simulation/gz/worlds/nfz_restricted_zone.sdf`)

> The world file's internal `<world name>` is `nfz_restricted_zone`, matching the
> file name, so `PX4_GZ_WORLD=nfz_restricted_zone` lines up with the Gazebo
> `/world/nfz_restricted_zone/create` service. This is required for `x500_depth`
> to spawn (a name mismatch causes `gz_bridge: Service call timed out`).

---

## 1. Launch PX4 + Gazebo (x500_depth, NFZ world, GUI visible)

```bash
cd /home/px4/PX4-Autopilot
export DISPLAY=:1                        # GUI on X display :1 (not headless)
export PX4_GZ_WORLD=nfz_restricted_zone  # NFZ world
make px4_sitl gz_x500_depth              # x500_depth + Gazebo GUI
```

Wait ~30–60 s for build + spawn. A successful boot logs:

```
INFO  [init] starting gazebo with world: .../gz/worlds/nfz_restricted_zone.sdf
INFO  [gz_bridge] world: nfz_restricted_zone, model name: x500_depth_0, simulation model: x500_depth
...
pxh>                                     # PX4 shell prompt = ready
```

## 2. Confirm the Gazebo GUI is visible (not headless)

```bash
export DISPLAY=:1

# GUI client process is running:
pgrep -af "gz sim -g"

# Gazebo window is present on the display:
xwininfo -root -tree | grep -i "Gazebo Sim"

# Scene contains the vehicle + NFZ (proves world + spawn, not just a blank GUI):
gz model --list | grep -E "x500_depth_0|no_fly_zone"
```

Capture a readiness screenshot (writes `00_gazebo_readiness_check/gazebo_gui_ready.png`):

```bash
cd /home/px4/collaboration/redteam
python -m tools.capture_gazebo_readiness --vehicle gz_x500_depth
```

Expected in the screenshot: "Gazebo Sim" title bar, green ground grid,
transparent **red NFZ prism**, and the **x500_depth** drone at the origin.

## 3. Restart cleanly before each PX4 run

Stale PX4/Gazebo processes cause spawn timeouts and mixed state. Reset first:

```bash
pkill -9 -f "bin/px4"        # stop PX4 SITL
pkill -9 -f "gz sim"         # stop Gazebo server + GUI
pkill -9 -f "ruby.*gz"       # stop any gz ruby wrappers
sleep 3
rm -f /tmp/px4_lock-0 /tmp/px4-sock-*   # clear PX4 SITL locks

# Verify clean (should print nothing / "CLEAN"):
ps -eo pid,args | grep -aE "gz sim|bin/px4" | grep -avE "grep|collaboration" || echo CLEAN
```

If a Gazebo server survives `pkill`, kill its process group:

```bash
PGID=$(ps -o pgid= -p "$(pgrep -f 'gz sim.*nfz_restricted' | head -1)" | tr -d ' ')
[ -n "$PGID" ] && kill -9 -"$PGID"
```

Then relaunch with step 1.

## 4. Run a selected LLM scenario against PX4

With PX4 + Gazebo running (step 1), in a second terminal:

```bash
cd /home/px4/collaboration/redteam

# One scenario (alias S2L–S8L or the numbered slug). Examples:
python run_experiment.py --scenario S5L --backend px4   # false policy clearance (inside NFZ)
python run_experiment.py --scenario S3L --backend px4   # runtime poison (through NFZ)
python run_experiment.py --scenario S8L --backend px4   # authority/confidence injection

# All LLM scenarios (S2L–S8L) in sequence:
python run_experiment.py --all-llm --backend px4
```

Scenario aliases: `S2L … S8L` (see `01_taxonomy/taxonomy_matrix.md`).
The LLM victim (`qwen2.5:7b`) is selected automatically for S2L–S8L.

## 5. Locate the resulting run folder and artifacts

PX4/Gazebo runs are written under `runs/gazebo/`:

```bash
cd /home/px4/collaboration/redteam
ls -dt runs/gazebo/*__*/ | head        # newest run first

RUN=$(ls -dt runs/gazebo/*__*/ | head -1)
ls "$RUN"
```

Each run folder (`<scenario_slug>__<YYYYMMDD_HHMMSS>/`) contains:

| File | Contents |
| --- | --- |
| `00_run_report.md` | Human-readable summary + verdict |
| `01_experiment_config.json` | Exact config used |
| `02_final_poisoned_memory.json` | Shared memory after the attack |
| `03_memory_audit_log.jsonl` | Every memory read/write (poison injection) |
| `04_flight_telemetry.csv` | Flight path (NED) |
| `05_breach_metrics.json` | NFZ entry time, depth, dwell, breach flag |
| `06_trajectory_map_2d_nfz.png` | 2D trajectory over the NFZ |
| `07_attack_replay_2d_animation.mp4` | Replay animation |
| `08_gazebo_flight_recording_3d.mp4` | Gazebo 3D recording (PX4 only, if enabled) |
| `09_gazebo_and_map_split_screen.mp4` | Split-screen (PX4 only, if enabled) |
| `10_llm_prompt.txt` / `11_llm_raw_response.txt` / `12_llm_parsed_action.json` / `13_llm_decisions.jsonl` | LLM evidence chain |

Sim (offline) runs go to `runs/sim/` instead; the frozen Phase 3 evaluation is
`runs/sim/llm_eval_final/` (curated in `../02_llm_sim_evaluation/`).

---

_Phase 4 attack scenarios are not run yet — this file documents the workflow only._
