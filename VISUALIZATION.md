# Visualization — what we built and how

We use **three layers** of visualization. Same NFZ everywhere:
`NORTH 5–12 m`, `EAST -3 to 3 m`.

---

## Layer 1 — 2D trajectory map (static PNG)

**File:** `06_trajectory_map_2d_nfz.png`  
**Tool:** `tools/plot_trajectory.py`

| Element | Color / symbol | Meaning |
|---------|----------------|---------|
| Red transparent rectangle | `#ff0000` @ 15% alpha | **No-Fly Zone** |
| Green dot | ● | Start position (after takeoff) |
| Blue line | — | Path under **benign** memory (mission_planner) |
| Red line | — | Path after **poisoned** memory (A0) |
| Black star | ★ | Poisoned target waypoint |
| Red X | ✕ | First NFZ breach point (+ timestamp in legend) |

**Data source:** `04_flight_telemetry.csv` (north, east, poisoned flag, inside_nfz).

This is **not Gazebo** — it is a top-down research map drawn with matplotlib.
Used for papers, slides, and the contact sheet.

---

## Layer 2 — 2D attack replay (animated MP4)

**File:** `07_attack_replay_2d_animation.mp4`  
**Tool:** `tools/animate_trajectory.py`

Same map as Layer 1, but plays back frame-by-frame with:

- Moving black dot = current drone position
- Benign path grows in blue, poisoned path in red
- **On-screen HUD:**
  ```text
  t =  9.22 s
  injection @ 8.0s  src=A0
  phase: POISONED by A0
  status: INSIDE NFZ
  ```

Shows **when** the attack happened and **when** the breach occurred.

---

## Layer 3 — 3D Gazebo world (visible red zone on ground)

**World file:** `gazebo/worlds/nfz_restricted_zone.sdf`  
**Launch:** `PX4_GZ_WORLD=nfz_restricted_zone make px4_sitl gz_x500`

A **red restricted area painted on the Gazebo ground** so you can see the NFZ
in 3D while the x500 drone flies. This is separate from the 2D matplotlib overlay
— both use the same NFZ coordinates.

**Recording:** `08_gazebo_flight_recording_3d.mp4` (screen capture during PX4 run).

---

## Layer 4 — Split screen (Gazebo + 2D map)

**File:** `09_gazebo_and_map_split_screen.mp4`  
**Tool:** `tools/make_split.py`

```text
┌─────────────────────┬─────────────────────┐
│  Gazebo 3D view     │  2D NFZ map replay  │
│  (real drone)       │  (red zone + path)  │
└─────────────────────┴─────────────────────┘
```

Left = what the simulator looks like. Right = what the research map shows.
Both aligned to the same mission timeline.

---

## Layer 5 — Contact sheet (all scenarios)

**File:** `runs/00_ALL_SCENARIOS_contact_sheet.png`  
**Tool:** `tools/plot_trajectory.py` → `contact_sheet()`

Five panels (one per scenario) in a single image for presentations.
Generated automatically when you run `python run_experiment.py --all`.

---

## Where red NFZ comes from (one definition)

```python
# config.py
NFZ = {"north_min": 5.0, "north_max": 12.0,
       "east_min": -3.0, "east_max": 3.0}
```

| Used by | Purpose |
|---------|---------|
| `world_model/nfz_geometry.py` | Breach detection during flight |
| `plot_trajectory.py` | Red rectangle on 2D maps |
| `animate_trajectory.py` | Red rectangle in animations |
| `nfz_restricted_zone.sdf` | Red zone on Gazebo ground |

---

## Optional future: 3D/2.5D prism animation

Not built yet (non-blocking). Would show the NFZ as a transparent red **prism**
in 3D with the drone path — useful for video but the 2D maps are the primary
research evidence.
