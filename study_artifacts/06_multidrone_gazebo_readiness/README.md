# Multi-drone Gazebo readiness check (swarm extension)

**Visual readiness only.** This folder proves the NFZ Gazebo world can display a
small `x500_depth` swarm (A0/A1/A2/A3) with the GUI visible, before any multi-PX4
swarm attack is attempted.

| File | Purpose |
| --- | --- |
| `gazebo_multidrone_ready.png` | Screenshot: 4 `x500_depth` drones + red NFZ prism, GUI visible |
| `model_metadata.md` | Vehicle/world/NFZ bounds, drone names, spawn positions, readiness type |
| `PX4_MULTIDRONE_COMMANDS.md` | Exact spawn workflow + documented PX4 multi-instance recipe |
| `launch.log` | Gazebo launch + per-drone spawn log |

## What this proves

- The `nfz_restricted_zone` world loads with **GUI visible (not headless)**.
- The **red transparent NFZ prism** renders (NORTH 5–12, EAST -3 to 3).
- **Four `x500_depth` drones** spawn and render together, placed **outside** the NFZ.

## What this does NOT prove

- No PX4 instances, no MAVLink, no offboard control, no flight.
- No swarm attack (SW0–SW3 remain **sim-only**; those results are unchanged).
- Multi-PX4 flight readiness is deferred to a later phase.

Regenerate: `python -m tools.capture_multidrone_readiness`
