# Multi-drone Gazebo readiness — model metadata

Visual proof that the NFZ Gazebo world can display a small **x500_depth** swarm
(A0/A1/A2/A3) before any multi-PX4 attack is attempted. See
`gazebo_multidrone_ready.png`.

## Configuration

| Field | Value |
| --- | --- |
| vehicle model | **`x500_depth`** |
| world | **`nfz_restricted_zone`** (`gazebo/worlds/nfz_restricted_zone.sdf`) |
| NFZ bounds | **NORTH 5–12, EAST -3 to 3** |
| GUI mode | **visible, not headless** (`DISPLAY=:1`, `gz sim` GUI client) |
| number of drones | **4** |
| drone names | A0, A1, A2, A3 |
| drones spawned this run | A0, A1, A2, A3 (4/4) |
| readiness type | **Gazebo VISUAL readiness only** — no PX4 instances, no MAVLink, no flight |

## Drone spawn positions

Gazebo ENU frame: **North = +Y, East = +X**. All drones spawn on the **Y=0
baseline in front of (outside) the NFZ** (the NFZ occupies Y ∈ [5,12]), spread
along East (X) so each is individually visible. Study NED mapping: north = Y,
east = X.

| Name | Model | ENU x (East) | ENU y (North) | Role |
| --- | --- | --- | --- | --- |
| **A0** | `x500_depth` | -4.5 | 0.0 | attacker (compromised memory writer) |
| **A1** | `x500_depth` | -1.5 | 0.0 | victim LLM UAV |
| **A2** | `x500_depth` | 1.5 | 0.0 | victim LLM UAV |
| **A3** | `x500_depth` | 4.5 | 0.0 | victim LLM UAV |

Spawn height: z = 0.18 m (rotor-rest on the ground plane).

## What this proves / does not prove

- **Proves:** the `nfz_restricted_zone` world loads with the GUI visible, the red
  transparent NFZ prism renders, and four `x500_depth` models can be placed and
  rendered together outside the NFZ.
- **Does NOT prove:** PX4 multi-instance flight, MAVLink connectivity, offboard
  control, or any swarm attack. Those are deferred to a later multi-PX4 phase.

## Exact scene command

```bash
export DISPLAY=:1
export GZ_SIM_RESOURCE_PATH=/home/px4/PX4-Autopilot/Tools/simulation/gz/models:/home/px4/PX4-Autopilot/Tools/simulation/gz/worlds
gz sim -r -v 2 /home/px4/collaboration/redteam/gazebo/worlds/nfz_restricted_zone.sdf
# then spawn each drone (see PX4_MULTIDRONE_COMMANDS.md)
```

Captured: `2026-07-04 17:53:18`  (regenerate:
`python -m tools.capture_multidrone_readiness`)
