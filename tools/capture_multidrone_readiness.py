"""Capture a Gazebo multi-drone VISUAL readiness screenshot (swarm extension).

Launches a standalone Gazebo GUI (not headless) with the NFZ world, then spawns
four `x500_depth` models named A0/A1/A2/A3 in front of (outside) the No-Fly-Zone
and screenshots the scene. This is a VISUAL readiness check only — it proves the
NFZ world can render a small x500_depth swarm; it does NOT start PX4 instances,
MAVLink, or any flight/attack behaviour.

Usage:
    python -m tools.capture_multidrone_readiness
    python -m tools.capture_multidrone_readiness --display :1
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# Reuse the proven window-finding + screenshot helpers from the single-drone check.
from tools.capture_gazebo_readiness import _find_gazebo_window, _screenshot  # noqa: E402

OUT_DIR = os.path.join(HERE, "study_artifacts", "06_multidrone_gazebo_readiness")
PX4_ROOT = os.environ.get("PX4_ROOT", os.path.expanduser("~/PX4-Autopilot"))
GZ_MODELS = os.path.join(PX4_ROOT, "Tools", "simulation", "gz", "models")
GZ_WORLDS = os.path.join(PX4_ROOT, "Tools", "simulation", "gz", "worlds")
REDTEAM_WORLD = os.path.join(HERE, "gazebo", "worlds", "nfz_restricted_zone.sdf")
X500_DEPTH_SDF = os.path.join(GZ_MODELS, "x500_depth", "model.sdf")

WORLD_NAME = "nfz_restricted_zone"
NFZ_BOUNDS = "NORTH 5–12, EAST -3 to 3"
VEHICLE = "x500_depth"

# Spawn poses in the Gazebo ENU frame (North=+Y, East=+X). The NFZ occupies
# Y in [5,12]; we place all four drones on the Y=0 baseline (well in front of /
# outside the zone), spread along East (X) so they are individually visible.
# Study NED mapping: north = Y, east = X.
DRONES = [
    {"name": "A0", "x": -4.5, "y": 0.0, "role": "attacker (compromised memory writer)"},
    {"name": "A1", "x": -1.5, "y": 0.0, "role": "victim LLM UAV"},
    {"name": "A2", "x": 1.5, "y": 0.0, "role": "victim LLM UAV"},
    {"name": "A3", "x": 4.5, "y": 0.0, "role": "victim LLM UAV"},
]
SPAWN_Z = 0.18


def _kill_stale() -> None:
    for pat in ("px4_sitl", "bin/px4", "gz sim", "ruby.*gz"):
        subprocess.run(["pkill", "-9", "-f", pat], stderr=subprocess.DEVNULL)
    time.sleep(3)


def _sim_env(display: str) -> dict:
    env = os.environ.copy()
    env["DISPLAY"] = display
    existing = env.get("GZ_SIM_RESOURCE_PATH", "")
    parts = [GZ_MODELS, GZ_WORLDS]
    if existing:
        parts.append(existing)
    env["GZ_SIM_RESOURCE_PATH"] = os.pathsep.join(parts)
    return env


def _world_ready(env: dict) -> bool:
    try:
        out = subprocess.check_output(["gz", "service", "-l"], env=env,
                                      text=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return f"/world/{WORLD_NAME}/create" in out


def _spawn_drone(env: dict, name: str, x: float, y: float, z: float, log) -> bool:
    req = (
        f'sdf_filename: "{X500_DEPTH_SDF}", name: "{name}", '
        f'pose: {{position: {{x: {x}, y: {y}, z: {z}}}}}'
    )
    cmd = [
        "gz", "service", "-s", f"/world/{WORLD_NAME}/create",
        "--reqtype", "gz.msgs.EntityFactory",
        "--reptype", "gz.msgs.Boolean",
        "--timeout", "5000",
        "--req", req,
    ]
    log.write(f"\n[spawn] {name} at ENU x={x} y={y} z={z}\n$ {' '.join(cmd)}\n")
    log.flush()
    try:
        res = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=30)
        log.write(res.stdout + res.stderr + "\n")
        log.flush()
        return "true" in res.stdout.lower()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        log.write(f"[spawn] {name} FAILED: {err}\n")
        log.flush()
        return False


def capture(display: str = ":1", wait_s: float = 60.0) -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.isfile(X500_DEPTH_SDF):
        print(f"[multidrone] ERROR: x500_depth model missing at {X500_DEPTH_SDF}",
              file=sys.stderr)
        return 1
    _kill_stale()
    env = _sim_env(display)

    log_path = os.path.join(OUT_DIR, "launch.log")
    log = open(log_path, "w")
    log.write(f"# Gazebo multi-drone visual readiness — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"DISPLAY={display}\nGZ_SIM_RESOURCE_PATH={env['GZ_SIM_RESOURCE_PATH']}\n")
    log.write(f"world={REDTEAM_WORLD}\nvehicle_model={X500_DEPTH_SDF}\n\n")
    log.flush()

    print(f"[multidrone] launching Gazebo GUI (world={WORLD_NAME}) on {display}…")
    gz = subprocess.Popen(
        ["gz", "sim", "-r", "-v", "2", REDTEAM_WORLD],
        cwd=HERE, env=env,
        stdout=log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )

    png = os.path.join(OUT_DIR, "gazebo_multidrone_ready.png")
    ok = False
    spawned: list[str] = []
    try:
        print("[multidrone] waiting for world service + GUI…")
        deadline = time.time() + wait_s
        world_up = False
        while time.time() < deadline:
            time.sleep(4)
            if _world_ready(env):
                world_up = True
                break
        if not world_up:
            print("[multidrone] WARNING: world create service not detected; "
                  "attempting spawn anyway", file=sys.stderr)
        time.sleep(3)
        for d in DRONES:
            if _spawn_drone(env, d["name"], d["x"], d["y"], SPAWN_Z, log):
                spawned.append(d["name"])
                print(f"[multidrone] spawned {d['name']}")
            time.sleep(1.5)
        print(f"[multidrone] spawned {len(spawned)}/4: {spawned}")

        # Let the scene render, then screenshot.
        for _ in range(6):
            time.sleep(4)
            if _find_gazebo_window(display):
                time.sleep(6)
                ok = _screenshot(display, png)
                if ok:
                    break
        if not ok:
            ok = _screenshot(display, png)
        print(f"[multidrone] {'saved ' + png if ok else 'screenshot FAILED'}")
    finally:
        print("[multidrone] stopping Gazebo…")
        try:
            os.killpg(os.getpgid(gz.pid), signal.SIGTERM)
            gz.wait(timeout=15)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(gz.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        log.close()

    _write_docs(display, spawned)
    return 0 if (ok and len(spawned) == 4) else 2


def _write_docs(display: str, spawned: list[str]) -> None:
    _write_metadata(display, spawned)
    _write_commands(display)
    _write_readme()


def _drone_table() -> str:
    rows = ["| Name | Model | ENU x (East) | ENU y (North) | Role |",
            "| --- | --- | --- | --- | --- |"]
    for d in DRONES:
        rows.append(f"| **{d['name']}** | `{VEHICLE}` | {d['x']} | {d['y']} | {d['role']} |")
    return "\n".join(rows)


def _write_metadata(display: str, spawned: list[str]) -> None:
    text = f"""# Multi-drone Gazebo readiness — model metadata

Visual proof that the NFZ Gazebo world can display a small **{VEHICLE}** swarm
(A0/A1/A2/A3) before any multi-PX4 attack is attempted. See
`gazebo_multidrone_ready.png`.

## Configuration

| Field | Value |
| --- | --- |
| vehicle model | **`{VEHICLE}`** |
| world | **`{WORLD_NAME}`** (`gazebo/worlds/{WORLD_NAME}.sdf`) |
| NFZ bounds | **{NFZ_BOUNDS}** |
| GUI mode | **visible, not headless** (`DISPLAY={display}`, `gz sim` GUI client) |
| number of drones | **4** |
| drone names | A0, A1, A2, A3 |
| drones spawned this run | {', '.join(spawned) if spawned else 'see launch.log'} ({len(spawned)}/4) |
| readiness type | **Gazebo VISUAL readiness only** — no PX4 instances, no MAVLink, no flight |

## Drone spawn positions

Gazebo ENU frame: **North = +Y, East = +X**. All drones spawn on the **Y=0
baseline in front of (outside) the NFZ** (the NFZ occupies Y ∈ [5,12]), spread
along East (X) so each is individually visible. Study NED mapping: north = Y,
east = X.

{_drone_table()}

Spawn height: z = {SPAWN_Z} m (rotor-rest on the ground plane).

## What this proves / does not prove

- **Proves:** the `{WORLD_NAME}` world loads with the GUI visible, the red
  transparent NFZ prism renders, and four `{VEHICLE}` models can be placed and
  rendered together outside the NFZ.
- **Does NOT prove:** PX4 multi-instance flight, MAVLink connectivity, offboard
  control, or any swarm attack. Those are deferred to a later multi-PX4 phase.

## Exact scene command

```bash
export DISPLAY={display}
export GZ_SIM_RESOURCE_PATH={GZ_MODELS}:{GZ_WORLDS}
gz sim -r -v 2 {REDTEAM_WORLD}
# then spawn each drone (see PX4_MULTIDRONE_COMMANDS.md)
```

Captured: `{time.strftime('%Y-%m-%d %H:%M:%S')}`  (regenerate:
`python -m tools.capture_multidrone_readiness`)
"""
    with open(os.path.join(OUT_DIR, "model_metadata.md"), "w") as f:
        f.write(text)


def _write_commands(display: str) -> None:
    spawn_lines = []
    for d in DRONES:
        req = (f'sdf_filename: "{X500_DEPTH_SDF}", name: "{d["name"]}", '
               f'pose: {{position: {{x: {d["x"]}, y: {d["y"]}, z: {SPAWN_Z}}}}}')
        spawn_lines.append(
            f'# {d["name"]} — {d["role"]}\n'
            f'gz service -s /world/{WORLD_NAME}/create \\\n'
            f'  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \\\n'
            f"  --timeout 5000 --req '{req}'"
        )
    spawns = "\n\n".join(spawn_lines)

    # Reference multi-instance PX4 recipe (documented, NOT run in this check).
    px4_multi = []
    base_port = 14540
    for i, d in enumerate(DRONES):
        px4_multi.append(
            f'# instance {i} -> {d["name"]}  (sysid {i + 1}, MAVLink udp {base_port + i})\n'
            f'PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="{d["x"]},{d["y"]}" \\\n'
            f'  PX4_SIM_MODEL=gz_{VEHICLE} PX4_GZ_STANDALONE=1 \\\n'
            f'  ./build/px4_sitl_default/bin/px4 -i {i}'
        )
    px4_block = "\n\n".join(px4_multi)

    text = f"""# Multi-drone Gazebo / PX4 commands

## A. Visual Gazebo multi-drone readiness (what this check runs)

This is the **visual-only** path used to produce `gazebo_multidrone_ready.png`.
It launches one Gazebo GUI and spawns four `{VEHICLE}` models directly — **no
PX4, no MAVLink**.

### 1. Launch the NFZ world with the GUI visible

```bash
export DISPLAY={display}
export GZ_SIM_RESOURCE_PATH={GZ_MODELS}:{GZ_WORLDS}
gz sim -r -v 2 {REDTEAM_WORLD}
```

Confirm the world create service is up:

```bash
gz service -l | grep /world/{WORLD_NAME}/create
```

### 2. Spawn the four drones (A0/A1/A2/A3), outside the NFZ

```bash
{spawns}
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
"""
    for i, d in enumerate(DRONES):
        text += f"| {d['name']} | {i} | {i + 1} | {base_port + i} | `gz_{VEHICLE}` |\n"
    text += f"""
```bash
export DISPLAY={display}
export PX4_GZ_WORLD={WORLD_NAME}
cd {PX4_ROOT}

{px4_block}
```

Clean stop for multi-instance:

```bash
pkill -9 -f "bin/px4"; pkill -9 -f "gz sim"
rm -f /tmp/px4_lock-* /tmp/px4-sock-*
```

> This section is a reference workflow only. The current readiness check is
> **visual Gazebo readiness** (section A); multi-PX4 is intentionally deferred.
"""
    with open(os.path.join(OUT_DIR, "PX4_MULTIDRONE_COMMANDS.md"), "w") as f:
        f.write(text)


def _write_readme() -> None:
    text = f"""# Multi-drone Gazebo readiness check (swarm extension)

**Visual readiness only.** This folder proves the NFZ Gazebo world can display a
small `{VEHICLE}` swarm (A0/A1/A2/A3) with the GUI visible, before any multi-PX4
swarm attack is attempted.

| File | Purpose |
| --- | --- |
| `gazebo_multidrone_ready.png` | Screenshot: 4 `{VEHICLE}` drones + red NFZ prism, GUI visible |
| `model_metadata.md` | Vehicle/world/NFZ bounds, drone names, spawn positions, readiness type |
| `PX4_MULTIDRONE_COMMANDS.md` | Exact spawn workflow + documented PX4 multi-instance recipe |
| `launch.log` | Gazebo launch + per-drone spawn log |

## What this proves

- The `{WORLD_NAME}` world loads with **GUI visible (not headless)**.
- The **red transparent NFZ prism** renders ({NFZ_BOUNDS}).
- **Four `{VEHICLE}` drones** spawn and render together, placed **outside** the NFZ.

## What this does NOT prove

- No PX4 instances, no MAVLink, no offboard control, no flight.
- No swarm attack (SW0–SW3 remain **sim-only**; those results are unchanged).
- Multi-PX4 flight readiness is deferred to a later phase.

Regenerate: `python -m tools.capture_multidrone_readiness`
"""
    with open(os.path.join(OUT_DIR, "README.md"), "w") as f:
        f.write(text)


def main() -> None:
    p = argparse.ArgumentParser(description="Capture Gazebo multi-drone visual readiness")
    p.add_argument("--display", default=os.environ.get("DISPLAY", ":1"))
    p.add_argument("--wait", type=float, default=60.0)
    args = p.parse_args()
    raise SystemExit(capture(args.display, args.wait))


if __name__ == "__main__":
    main()
