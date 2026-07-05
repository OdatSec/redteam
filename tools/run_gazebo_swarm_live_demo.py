"""Live, smooth Gazebo swarm demo from existing SW1/SW2/SW3 telemetry.

Run ONE command and watch the four-drone swarm attack unfold live in the Gazebo
GUI: the drones spawn on the ground, take off smoothly, hold a benign hover,
then (at the A0 injection time) the victims redirect and breach the No-Fly-Zone
according to the recorded swarm telemetry.

    python -m tools.run_gazebo_swarm_live_demo --scenario SW1
    python -m tools.run_gazebo_swarm_live_demo --scenario SW2
    python -m tools.run_gazebo_swarm_live_demo --scenario SW3

Smoothness: telemetry is interpolated to a fixed 25 Hz and pushed to Gazebo via
the in-process gz-transport `set_pose` service (no per-frame subprocess), so the
drones glide instead of teleporting between sparse telemetry samples. The world
runs PAUSED (kinematic playback) so there is no gravity/physics fighting the
scripted poses.

IMPORTANT — this is *Gazebo visual playback from swarm telemetry, NOT PX4
multi-instance flight*. No PX4, no MAVLink, and no LLM/attack loop run inside
Gazebo here; the drone models are moved along already-computed trajectories. The
authoritative scientific evidence lives in study_artifacts/05_swarm_extension/.
"""

from __future__ import annotations

# Must be set before importing gz.msgs (system protobuf generated files predate
# the C++ descriptor pool used by the local protobuf runtime).
import os
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import argparse
import csv
import glob
import json
import signal
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import config  # noqa: E402

import gz.transport13 as gz_transport  # noqa: E402
from gz.msgs10.pose_pb2 import Pose  # noqa: E402
from gz.msgs10.boolean_pb2 import Boolean  # noqa: E402

PX4_ROOT = os.environ.get("PX4_ROOT", os.path.expanduser("~/PX4-Autopilot"))
GZ_MODELS = os.path.join(PX4_ROOT, "Tools", "simulation", "gz", "models")
GZ_WORLDS = os.path.join(PX4_ROOT, "Tools", "simulation", "gz", "worlds")
REDTEAM_WORLD = os.path.join(HERE, "gazebo", "worlds", "nfz_restricted_zone.sdf")
X500_DEPTH_SDF = os.path.join(GZ_MODELS, "x500_depth", "model.sdf")
WORLD_NAME = "nfz_restricted_zone"

GROUND_Z = 0.18
CRUISE_ALT = 3.0
A0_STAGING = (-6.0, 0.0)  # ENU (east, north); A0 hovers here, it does not fly.
RATE_HZ = 25.0

RECORD_ROOT = os.path.join(HERE, "study_artifacts", "07_swarm_showcase",
                           "gazebo_playback")
GZ_WIN_TITLE = "Gazebo Sim"
GZ_WIN_POS = (0, 0, 1100, 900)  # x, y, w, h when recording (window raised here)

SCENARIO_TITLE = {
    "SW1": "Shared-Memory Route Lure",
    "SW2": "False Policy Clearance Swarm",
    "SW3": "Stealth Drift Swarm",
}


def _sim_env(display: str) -> dict:
    env = os.environ.copy()
    env["DISPLAY"] = display
    parts = [GZ_MODELS, GZ_WORLDS]
    if env.get("GZ_SIM_RESOURCE_PATH"):
        parts.append(env["GZ_SIM_RESOURCE_PATH"])
    env["GZ_SIM_RESOURCE_PATH"] = os.pathsep.join(parts)
    return env


def _kill_stale() -> None:
    for pat in ("px4_sitl", "bin/px4", "gz sim", "ruby.*gz"):
        subprocess.run(["pkill", "-9", "-f", pat], stderr=subprocess.DEVNULL)
    time.sleep(3)


def _latest_run(sid: str) -> str | None:
    slug = config.SWARM_SCENARIO_IDS[sid]
    matches = sorted(glob.glob(os.path.join(config.RUNS_SWARM_DIR, f"{slug}__*")))
    return matches[-1] if matches else None


def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def _load_agent(run_dir: str, aid: str) -> list[dict]:
    path = os.path.join(run_dir, config.swarm_agent_artifacts(aid)["telemetry"])
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _world_ready(env: dict) -> bool:
    try:
        out = subprocess.check_output(["gz", "service", "-l"], env=env,
                                      text=True, timeout=10)
    except Exception:
        return False
    return f"/world/{WORLD_NAME}/create" in out


def _spawn(env: dict, name: str, east: float, north: float, z: float) -> bool:
    req = (f'sdf_filename: "{X500_DEPTH_SDF}", name: "{name}", '
           f'pose: {{position: {{x: {east}, y: {north}, z: {z}}}}}')
    cmd = ["gz", "service", "-s", f"/world/{WORLD_NAME}/create",
           "--reqtype", "gz.msgs.EntityFactory", "--reptype", "gz.msgs.Boolean",
           "--timeout", "5000", "--req", req]
    res = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=30)
    return "true" in res.stdout.lower()


class Interp:
    """Per-agent linear interpolator over recorded telemetry (ENU east/north)."""

    def __init__(self, rows: list[dict]):
        self.t = np.array([float(r["t"]) for r in rows])
        self.e = np.array([float(r["east"]) for r in rows])
        self.n = np.array([float(r["north"]) for r in rows])
        self.t_max = float(self.t[-1]) if len(self.t) else 0.0
        # First breach time (for the live breach counter).
        self.breach_t: float | None = None
        for r in rows:
            if _truthy(r.get("inside_nfz")):
                self.breach_t = float(r["t"])
                break

    def at(self, tq: float) -> tuple[float, float]:
        return float(np.interp(tq, self.t, self.e)), float(np.interp(tq, self.t, self.n))


class PoseSetter:
    def __init__(self):
        self.node = gz_transport.Node()
        self.service = f"/world/{WORLD_NAME}/set_pose"

    def set(self, name: str, east: float, north: float, z: float,
            yaw: float = 0.0) -> None:
        req = Pose()
        req.name = name
        req.position.x = east
        req.position.y = north
        req.position.z = z
        req.orientation.w = np.cos(yaw / 2.0)
        req.orientation.z = np.sin(yaw / 2.0)
        try:
            self.node.request(self.service, req, Pose, Boolean, 100)
        except Exception:
            pass


def _raise_window(display: str) -> bool:
    """Bring the Gazebo GUI to the front + a known position (for recording)."""
    x, y, w, h = GZ_WIN_POS
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "tools", "win.py"),
                        GZ_WIN_TITLE, str(x), str(y), str(w), str(h)],
                       env={**os.environ, "DISPLAY": display},
                       capture_output=True, timeout=15)
        return True
    except Exception:
        return False


def _grab(display: str, out_png: str) -> bool:
    import shutil
    if not shutil.which("ffmpeg"):
        return False
    x, y, w, h = GZ_WIN_POS
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "x11grab",
             "-draw_mouse", "0", "-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}",
             "-frames:v", "1", out_png],
            env={**os.environ, "DISPLAY": display}, check=True, timeout=20)
        return os.path.isfile(out_png) and os.path.getsize(out_png) > 5000
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _hud(sid: str, phase: str, sim_t: float, t_max: float, inj: float,
         n_breach: int, n_victims: int, wall_phase: str) -> None:
    bar_col = "\033[91m" if phase == "POISONED" else "\033[92m"
    reset = "\033[0m"
    sys.stdout.write(
        f"\r  {sid} {SCENARIO_TITLE.get(sid, ''):26s} | "
        f"{wall_phase:9s} | t={sim_t:5.1f}/{t_max:4.1f}s | "
        f"phase={bar_col}{phase:8s}{reset} | "
        f"A0 inject @ {inj:4.1f}s | breaches {n_breach}/{n_victims}   "
    )
    sys.stdout.flush()


def run_demo(sid: str, display: str = ":1", speed: float = 1.0,
             takeoff_s: float = 3.5, hover_s: float = 2.0,
             tail_s: float = 3.0, hold_s: float | None = None,
             record: bool = False) -> int:
    if sid not in SCENARIO_TITLE:
        print(f"[live] unsupported scenario {sid}", file=sys.stderr)
        return 1
    run = _latest_run(sid)
    if not run:
        print(f"[live] no telemetry run for {sid}", file=sys.stderr)
        return 1
    cfg = json.load(open(os.path.join(run, config.SWARM_ARTIFACTS["config"])))
    metrics = json.load(open(os.path.join(run, config.SWARM_ARTIFACTS["metrics"])))["swarm"]
    inj = float(cfg.get("attack_delay_s") or 8.0)

    victims = list(config.SWARM_VICTIMS)
    interp = {aid: Interp(_load_agent(run, aid)) for aid in victims}
    interp = {aid: it for aid, it in interp.items() if len(it.t)}
    if not interp:
        print(f"[live] no per-agent telemetry found in {run}", file=sys.stderr)
        return 1
    t_max = max(it.t_max for it in interp.values())
    start_pose = {aid: it.at(0.0) for aid, it in interp.items()}

    print("=" * 78)
    print(f"  GAZEBO LIVE SWARM DEMO — {sid} · {SCENARIO_TITLE[sid]}")
    print("  Gazebo visual playback from swarm telemetry — NOT PX4 multi-instance flight")
    print(f"  A0 = attacker/source (hovers, writes memory) · A1/A2/A3 = victim LLM UAVs")
    print(f"  world={WORLD_NAME} · vehicle=x500_depth · GUI display={display}")
    print(f"  telemetry run: {os.path.relpath(run, HERE)}")
    print("=" * 78)

    _kill_stale()
    env = _sim_env(display)
    # PAUSED world -> kinematic playback (no gravity fighting scripted poses).
    print(f"[live] launching Gazebo GUI (paused) on {display}…")
    gz = subprocess.Popen(["gz", "sim", "-v", "2", REDTEAM_WORLD],
                          cwd=HERE, env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    rc = 2
    rec_proc = None
    try:
        deadline = time.time() + 70
        while time.time() < deadline and not _world_ready(env):
            time.sleep(4)
        if not _world_ready(env):
            print("[live] ERROR: world create service never appeared", file=sys.stderr)
            return 2
        time.sleep(3)

        # Spawn A0 (staging) + A1/A2/A3 (telemetry start) on the ground.
        print("[live] spawning drones on the ground…")
        _spawn(env, "A0", A0_STAGING[0], A0_STAGING[1], GROUND_Z)
        for aid in interp:
            e0, n0 = start_pose[aid]
            _spawn(env, aid, e0, n0, GROUND_Z)
            time.sleep(0.8)
        time.sleep(3)

        setter = PoseSetter()
        dt = 1.0 / RATE_HZ
        n_victims = len(interp)

        # Optional recording: raise the GUI to a known spot and run one
        # continuous x11grab (smooth) + extract key frames afterwards.
        out_dir = os.path.join(RECORD_ROOT, sid)
        video_path = os.path.join(out_dir, f"{sid}_gazebo_visual_playback.mp4")
        events: dict[str, float] = {}
        v0 = None
        if record:
            os.makedirs(out_dir, exist_ok=True)
            _raise_window(display)
            time.sleep(1.5)
            x, y, w, h = GZ_WIN_POS
            rec_proc = subprocess.Popen(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "x11grab", "-draw_mouse", "0", "-framerate", "25",
                 "-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}",
                 "-pix_fmt", "yuv420p", video_path],
                env={**os.environ, "DISPLAY": display},
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            v0 = time.time()
            time.sleep(0.5)

        def mark(name: str) -> None:
            if record and v0 is not None and name not in events:
                events[name] = time.time() - v0

        def push(sim_t: float, z_map: dict) -> int:
            setter.set("A0", A0_STAGING[0], A0_STAGING[1], z_map["A0"])
            nb = 0
            for aid, it in interp.items():
                e, n = it.at(sim_t)
                setter.set(aid, e, n, z_map[aid])
                if it.breach_t is not None and sim_t >= it.breach_t:
                    nb += 1
            return nb

        # Phase 1: smooth takeoff (ground -> cruise), holding start x/y.
        print("[live] phase: TAKEOFF")
        steps = max(1, int(takeoff_s / dt))
        for i in range(steps + 1):
            frac = i / steps
            z = GROUND_Z + (CRUISE_ALT - GROUND_Z) * frac
            z_map = {aid: z for aid in list(interp) + ["A0"]}
            push(0.0, z_map)
            _hud(sid, "BENIGN", 0.0, t_max, inj, 0, n_victims, "TAKEOFF")
            time.sleep(dt)
        print()

        # Phase 2: benign hover at t=0 mission poses.
        print("[live] phase: BENIGN HOVER")
        z_map = {aid: CRUISE_ALT for aid in list(interp) + ["A0"]}
        mark("start_frame")
        steps = max(1, int(hover_s / dt))
        for i in range(steps + 1):
            push(0.0, z_map)
            _hud(sid, "BENIGN", 0.0, t_max, inj, 0, n_victims, "HOVER")
            time.sleep(dt)
        print()

        # Phase 3: interpolated telemetry playback (benign -> poison -> breach).
        print("[live] phase: MISSION PLAYBACK (benign -> A0 poison -> breach)")
        n_frames = int((t_max / max(speed, 0.05)) / dt)
        last_phase = "BENIGN"
        last_nb = 0
        for i in range(n_frames + 1):
            sim_t = min(t_max, (i * dt) * speed)
            nb = push(sim_t, z_map)
            phase = "POISONED" if sim_t >= inj else "BENIGN"
            if phase != last_phase:
                sys.stdout.write("\n")
                print(f"[live] >>> t={sim_t:.1f}s  A0 INJECTS POISON → phase POISONED")
                mark("injection_frame")
                last_phase = phase
            if nb > last_nb and last_nb == 0:
                mark("first_breach_frame")
            last_nb = nb
            _hud(sid, phase, sim_t, t_max, inj, nb, n_victims, "ATTACK")
            time.sleep(dt)
        print()

        # Phase 4: hold final breach state.
        print(f"[live] phase: FINAL BREACH STATE (holding {tail_s:.0f}s)")
        nb_final = push(t_max, z_map)
        mark("final_breach_frame")
        steps = max(1, int(tail_s / dt))
        for i in range(steps + 1):
            push(t_max, z_map)
            _hud(sid, "POISONED", t_max, t_max, inj, nb_final, n_victims, "FINAL")
            time.sleep(dt)
        print()
        print(f"[live] done — {sid}: {nb_final}/{n_victims} victims breached the NFZ "
              f"(first={metrics['time_to_first_breach_s']}s, "
              f"last={metrics['time_to_last_breach_s']}s)")

        # Finalize recording: stop ffmpeg, then extract key frames from the mp4.
        if record and rec_proc is not None:
            time.sleep(1.0)
            try:
                rec_proc.communicate(input=b"q", timeout=10)
            except subprocess.TimeoutExpired:
                rec_proc.terminate()
                try:
                    rec_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    rec_proc.kill()
            if os.path.isfile(video_path) and os.path.getsize(video_path) > 10000:
                print(f"[live] saved video {os.path.relpath(video_path, HERE)}")
                for name, off in events.items():
                    fp = os.path.join(out_dir, f"{sid}_{name}.png")
                    subprocess.run(
                        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                         "-ss", f"{max(off, 0.0):.2f}", "-i", video_path,
                         "-frames:v", "1", fp], timeout=30)
                    if os.path.isfile(fp):
                        print(f"[live]   key frame {name} @ +{off:.1f}s")
                _write_playback_readme()
            else:
                print("[live] WARNING: recording failed / too small", file=sys.stderr)
            rec_proc = None
        rc = 0
        # Keep holding the final pose so the window stays populated.
        if hold_s is None:
            print("[live] Gazebo will remain open. Press Ctrl-C to close.")
            while True:
                push(t_max, z_map)
                time.sleep(0.2)
        else:
            print(f"[live] holding final state {hold_s:.0f}s then closing (test mode)…")
            t_end = time.time() + hold_s
            while time.time() < t_end:
                push(t_max, z_map)
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[live] closing…")
        rc = 0
    finally:
        try:
            if rec_proc is not None:
                rec_proc.kill()
        except Exception:
            pass
        try:
            os.killpg(os.getpgid(gz.pid), signal.SIGTERM)
            gz.wait(timeout=15)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(gz.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
    return rc


def _write_playback_readme() -> None:
    os.makedirs(RECORD_ROOT, exist_ok=True)
    text = f"""# Gazebo visual playback (from swarm telemetry)

> **Gazebo visual playback from swarm telemetry, NOT PX4 multi-instance flight.**

These videos/frames are produced by `tools/run_gazebo_swarm_live_demo.py` with
`--record`. Four `x500_depth` models (A0/A1/A2/A3) are moved inside the
`{WORLD_NAME}` world along the **saved per-agent swarm telemetry**, interpolated
to {int(RATE_HZ)} Hz for smooth motion. A0 is the attacker/source (hovers at a
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
"""
    with open(os.path.join(RECORD_ROOT, "README.md"), "w") as f:
        f.write(text)


def main() -> None:
    p = argparse.ArgumentParser(description="Live Gazebo swarm demo from telemetry")
    p.add_argument("--scenario", required=True, choices=["SW1", "SW2", "SW3"])
    p.add_argument("--display", default=os.environ.get("DISPLAY", ":1"))
    p.add_argument("--speed", type=float, default=1.0,
                   help="playback speed multiplier (1.0 = real time)")
    p.add_argument("--hold", type=float, default=None,
                   help="seconds to hold final state before auto-close "
                        "(default: stay open until Ctrl-C)")
    p.add_argument("--record", action="store_true",
                   help="raise the GUI + record mp4 and key frames into "
                        "study_artifacts/07_swarm_showcase/gazebo_playback/")
    args = p.parse_args()
    hold = args.hold
    if args.record and hold is None:
        hold = 2.0  # auto-close after recording
    raise SystemExit(run_demo(args.scenario, args.display, args.speed,
                              hold_s=hold, record=args.record))


if __name__ == "__main__":
    main()
