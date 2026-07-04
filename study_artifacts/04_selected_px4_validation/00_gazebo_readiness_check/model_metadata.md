# Gazebo readiness check — model metadata

Visual proof that the PX4/Gazebo stack is ready for Phase 4 validation:
GUI is **visible (not headless)**, the **x500_depth** vehicle spawns, the NFZ
world loads, and the **red transparent NFZ prism** renders on the ground.

See `gazebo_gui_ready.png` in this folder.

## Configuration

| Field | Value |
| --- | --- |
| LLM model | `qwen2.5:7b` (Ollama, local `http://localhost:11434`) |
| vehicle model | **`x500_depth`** (PX4 target `gz_x500_depth`) |
| PX4/Gazebo model command | `PX4_GZ_WORLD=nfz_restricted_zone make px4_sitl gz_x500_depth` |
| world file used | `gazebo/worlds/nfz_restricted_zone.sdf` (world name: `nfz_restricted_zone`) |
| backend | PX4/Gazebo (SITL + gz sim) |
| GUI mode | **visible, not headless** (`DISPLAY=:1`, `gz sim -g` GUI client running) |
| NFZ bounds | **NORTH 5–12, EAST −3 to 3** (ENU: gz Y ∈ [5,12], gz X ∈ [−3,3]) |

## Visual checklist (verified in `gazebo_gui_ready.png`)

- [x] Gazebo GUI window is open (title bar "Gazebo Sim") — not background/headless
- [x] Vehicle model **`x500_depth`** spawned at origin (visible on the grid)
- [x] Transparent **red NFZ prism** visible on the ground (NORTH 5–12, EAST ±3)
- [x] NFZ world loaded correctly (`world: nfz_restricted_zone`)

## Spawn confirmation (from live SITL boot)

```
INFO  [init] starting gazebo with world: .../gz/worlds/nfz_restricted_zone.sdf
INFO  [gz_bridge] world: nfz_restricted_zone, model name: x500_depth_0, simulation model: x500_depth
```

Gazebo scene models present: `ground_plane`, `no_fly_zone` (red prism), `x500_depth_0`.
Create service offered: `/world/nfz_restricted_zone/create`.

## Exact launch command

```bash
cd /home/px4/PX4-Autopilot
export DISPLAY=:1                       # X display with GUI (not headless)
export PX4_GZ_WORLD=nfz_restricted_zone # NFZ world (world name matches file)
make px4_sitl gz_x500_depth            # x500_depth vehicle + Gazebo GUI
```

World source (symlinked into PX4 worlds dir):
`/home/px4/collaboration/redteam/gazebo/worlds/nfz_restricted_zone.sdf`

> Note: the world file's internal `<world name>` was aligned to
> `nfz_restricted_zone` so `PX4_GZ_WORLD=nfz_restricted_zone` matches the
> Gazebo `/world/<name>/create` service. This is what lets `x500_depth`
> spawn reliably instead of timing out.

Full workflow: see `../PX4_GAZEBO_COMMANDS.md`.

Captured: `2026-07-04 13:00`
