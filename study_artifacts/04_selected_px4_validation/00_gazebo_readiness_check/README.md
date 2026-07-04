# Gazebo readiness check (Phase 4 prep)

Visual proof that Gazebo runs with **GUI visible** (not headless), showing the
**x500_depth** drone and the red transparent NFZ prism before any PX4
validation runs.

| File | Purpose |
| --- | --- |
| `gazebo_gui_ready.png` | Screenshot of Gazebo GUI (x500_depth drone + red NFZ prism) |
| `model_metadata.md` | LLM model, vehicle (`x500_depth`), world, NFZ bounds, launch command |
| `launch.log` | PX4 SITL stdout from the successful capture run |

Regenerate: `python -m tools.capture_gazebo_readiness --vehicle gz_x500_depth`

Full workflow: [`../PX4_GAZEBO_COMMANDS.md`](../PX4_GAZEBO_COMMANDS.md)
