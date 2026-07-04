# Multi-drone Gazebo / PX4 commands

## A. Visual Gazebo multi-drone readiness (what this check runs)

This is the **visual-only** path used to produce `gazebo_multidrone_ready.png`.
It launches one Gazebo GUI and spawns four `x500_depth` models directly — **no
PX4, no MAVLink**.

### 1. Launch the NFZ world with the GUI visible

```bash
export DISPLAY=:1
export GZ_SIM_RESOURCE_PATH=/home/px4/PX4-Autopilot/Tools/simulation/gz/models:/home/px4/PX4-Autopilot/Tools/simulation/gz/worlds
gz sim -r -v 2 /home/px4/collaboration/redteam/gazebo/worlds/nfz_restricted_zone.sdf
```

Confirm the world create service is up:

```bash
gz service -l | grep /world/nfz_restricted_zone/create
```

### 2. Spawn the four drones (A0/A1/A2/A3), outside the NFZ

```bash
# A0 — attacker (compromised memory writer)
gz service -s /world/nfz_restricted_zone/create \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 5000 --req 'sdf_filename: "/home/px4/PX4-Autopilot/Tools/simulation/gz/models/x500_depth/model.sdf", name: "A0", pose: {position: {x: -4.5, y: 0.0, z: 0.18}}'

# A1 — victim LLM UAV
gz service -s /world/nfz_restricted_zone/create \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 5000 --req 'sdf_filename: "/home/px4/PX4-Autopilot/Tools/simulation/gz/models/x500_depth/model.sdf", name: "A1", pose: {position: {x: -1.5, y: 0.0, z: 0.18}}'

# A2 — victim LLM UAV
gz service -s /world/nfz_restricted_zone/create \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 5000 --req 'sdf_filename: "/home/px4/PX4-Autopilot/Tools/simulation/gz/models/x500_depth/model.sdf", name: "A2", pose: {position: {x: 1.5, y: 0.0, z: 0.18}}'

# A3 — victim LLM UAV
gz service -s /world/nfz_restricted_zone/create \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 5000 --req 'sdf_filename: "/home/px4/PX4-Autopilot/Tools/simulation/gz/models/x500_depth/model.sdf", name: "A3", pose: {position: {x: 4.5, y: 0.0, z: 0.18}}'
```

### 3. Clean stop / restart

```bash
pkill -9 -f "gz sim"
```

One command reproduces the whole check:

```bash
python -m tools.capture_multidrone_readiness
```

## B. PX4 multi-instance recipe (DOCUMENTED ONLY — not run yet)

For a later multi-PX4 phase, each drone would be a separate PX4 SITL instance
sharing one Gazebo server (the first instance starts Gazebo; the rest attach via
`PX4_GZ_STANDALONE=1`). System IDs and MAVLink ports below are the intended
convention.

| Drone | PX4 instance `-i` | System ID | MAVLink UDP | Model |
| --- | --- | --- | --- | --- |
| A0 | 0 | 1 | 14540 | `gz_x500_depth` |
| A1 | 1 | 2 | 14541 | `gz_x500_depth` |
| A2 | 2 | 3 | 14542 | `gz_x500_depth` |
| A3 | 3 | 4 | 14543 | `gz_x500_depth` |

```bash
export DISPLAY=:1
export PX4_GZ_WORLD=nfz_restricted_zone
cd /home/px4/PX4-Autopilot

# instance 0 -> A0  (sysid 1, MAVLink udp 14540)
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="-4.5,0.0" \
  PX4_SIM_MODEL=gz_x500_depth PX4_GZ_STANDALONE=1 \
  ./build/px4_sitl_default/bin/px4 -i 0

# instance 1 -> A1  (sysid 2, MAVLink udp 14541)
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="-1.5,0.0" \
  PX4_SIM_MODEL=gz_x500_depth PX4_GZ_STANDALONE=1 \
  ./build/px4_sitl_default/bin/px4 -i 1

# instance 2 -> A2  (sysid 3, MAVLink udp 14542)
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="1.5,0.0" \
  PX4_SIM_MODEL=gz_x500_depth PX4_GZ_STANDALONE=1 \
  ./build/px4_sitl_default/bin/px4 -i 2

# instance 3 -> A3  (sysid 4, MAVLink udp 14543)
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="4.5,0.0" \
  PX4_SIM_MODEL=gz_x500_depth PX4_GZ_STANDALONE=1 \
  ./build/px4_sitl_default/bin/px4 -i 3
```

Clean stop for multi-instance:

```bash
pkill -9 -f "bin/px4"; pkill -9 -f "gz sim"
rm -f /tmp/px4_lock-* /tmp/px4-sock-*
```

> This section is a reference workflow only. The current readiness check is
> **visual Gazebo readiness** (section A); multi-PX4 is intentionally deferred.
