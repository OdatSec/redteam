# Gazebo visual playback (from swarm telemetry)

> **Gazebo visual playback from swarm telemetry, NOT PX4 multi-instance flight.**

These videos/frames are produced by `tools/run_gazebo_swarm_live_demo.py` with
`--record`. Four `x500_depth` models (A0/A1/A2/A3) are moved inside the
`nfz_restricted_zone` world along the **saved per-agent swarm telemetry**, interpolated
to 25 Hz for smooth motion. A0 is the attacker/source (hovers at a
staging pose; it writes memory, it does not fly); A1/A2/A3 follow their recorded
trajectories through the red No-Fly-Zone.

**Not** PX4, MAVLink, or the LLM/attack loop running inside Gazebo. No flight
dynamics are simulated during playback (the world is paused; poses are scripted).
The authoritative attack evidence is the sim telemetry in
`../../05_swarm_extension/`.

Per scenario (`SW1/`, `SW2/`, `SW3/`):

| File | Meaning |
| --- | --- |
| `SWx_gazebo_visual_playback.mp4` | Smooth live-demo recording (takeoff → benign → poison → breach) |
| `SWx_start_frame.png` | Fleet hovering, benign mission |
| `SWx_injection_frame.png` | A0 poison injection (t≈8 s) |
| `SWx_first_breach_frame.png` | First victim entering the NFZ |
| `SWx_final_breach_frame.png` | Final swarm breach state |

Run it live (Gazebo GUI opens in front of you):

```bash
python -m tools.run_gazebo_swarm_live_demo --scenario SW1
```

Re-record the clips/frames:

```bash
python -m tools.run_gazebo_swarm_live_demo --scenario SW1 --record --hold 2
```
