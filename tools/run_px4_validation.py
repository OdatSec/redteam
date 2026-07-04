"""Phase 4: selected PX4/Gazebo validation for LLM memory-poisoning scenarios.

For a given scenario this script:
  1. Cleanly restarts PX4 SITL + Gazebo (GUI visible, x500_depth, NFZ world).
  2. Waits for PX4 to be ready (MAVLink up).
  3. Runs the scenario through the existing harness (run_experiment.run_scenario,
     backend=px4), preserving the full evidence chain in a timestamped run folder.
  4. Concurrently captures two Gazebo frames into that run folder:
       - gazebo_start_frame.png  (drone airborne, pre-breach)
       - gazebo_breach_frame.png (first telemetry row with inside_nfz=True)
  5. Writes RUN_COMMAND.md documenting the exact launch + run commands.
  6. Cleanly stops PX4/Gazebo.

Usage:
    python -m tools.run_px4_validation --scenario S3L
    python -m tools.run_px4_validation --scenario S5L --vehicle gz_x500_depth
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import run_experiment  # noqa: E402

PX4_ROOT = os.environ.get("PX4_ROOT", os.path.expanduser("~/PX4-Autopilot"))
DISPLAY = os.environ.get("DISPLAY", ":1")
WORLD = "nfz_restricted_zone"


# --------------------------------------------------------------------------- #
# process management
# --------------------------------------------------------------------------- #
def _sh(cmd: str) -> None:
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def clean_px4_gz() -> None:
    """Kill any leftover PX4/Gazebo so each scenario starts from a clean slate."""
    _sh("pkill -9 -f 'bin/px4'")
    _sh("pkill -9 -f 'gz sim'")
    _sh("pkill -9 -f 'ruby.*gz'")
    time.sleep(3)
    # kill surviving gz server by process group
    out = subprocess.run(
        "pgrep -f 'gz sim' | head -1", shell=True, text=True,
        capture_output=True).stdout.strip()
    if out:
        pgid = subprocess.run(
            f"ps -o pgid= -p {out}", shell=True, text=True,
            capture_output=True).stdout.strip()
        if pgid:
            _sh(f"kill -9 -{pgid}")
    _sh("rm -f /tmp/px4_lock-0 /tmp/px4-sock-*")
    time.sleep(2)


def launch_px4(vehicle: str, log_path: str, ready_timeout: float = 120.0):
    """Launch PX4 SITL + Gazebo GUI; return Popen once MAVLink/pxh is ready."""
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    env["PX4_GZ_WORLD"] = WORLD
    print(f"[px4] launching {vehicle} + Gazebo GUI (world={WORLD}, DISPLAY={DISPLAY})")
    proc = subprocess.Popen(
        ["make", "px4_sitl", vehicle],
        cwd=PX4_ROOT, env=env,
        stdout=open(log_path, "w"), stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    deadline = time.time() + ready_timeout
    ready = False
    while time.time() < deadline:
        time.sleep(3)
        try:
            with open(log_path, errors="ignore") as fh:
                txt = fh.read()
        except FileNotFoundError:
            txt = ""
        if "Ready for takeoff" in txt or txt.count("pxh>") > 0:
            if "simulation model: " in txt:
                ready = True
                break
        if "failed to start and spawn model" in txt:
            raise RuntimeError("gz_bridge failed to spawn model (see log)")
        if proc.poll() is not None:
            raise RuntimeError("PX4 process exited during startup (see log)")
    if not ready:
        raise RuntimeError("PX4 did not reach ready state in time")
    print("[px4] ready (MAVLink up, model spawned)")
    time.sleep(3)
    return proc


def stop_px4(proc) -> None:
    print("[px4] stopping PX4/Gazebo")
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    clean_px4_gz()


# --------------------------------------------------------------------------- #
# gazebo window capture
# --------------------------------------------------------------------------- #
def _gz_window():
    """Return (window_obj, display) for the 'Gazebo Sim' window, or (None, d)."""
    from Xlib import X, display
    d = display.Display(DISPLAY)
    root = d.screen().root
    stack = d.intern_atom("_NET_CLIENT_LIST_STACKING")
    prop = root.get_full_property(stack, X.AnyPropertyType)
    if not prop:
        return None, d
    for wid in prop.value:
        w = d.create_resource_object("window", wid)
        try:
            n = w.get_wm_name()
        except Exception:
            n = None
        if n and "Gazebo Sim" in str(n):
            return w, d
    return None, d


_GZ_GEOM: dict = {}  # cached (x, y, w, h) of the raised Gazebo window


def raise_gz_window() -> bool:
    """Bring the Gazebo window to the front once and cache its geometry."""
    try:
        from Xlib import X
        from Xlib.protocol import event
    except Exception:
        return False
    w, d = _gz_window()
    if w is None:
        return False
    root = d.screen().root
    net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
    ev = event.ClientMessage(window=w, client_type=net_active,
                             data=(32, [1, X.CurrentTime, 0, 0, 0]))
    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    w.configure(stack_mode=X.Above)
    d.sync()
    time.sleep(1.2)
    g = w.get_geometry()
    coords = w.translate_coords(root, 0, 0)
    _GZ_GEOM["geom"] = (-coords.x, -coords.y, g.width, g.height)
    return True


def grab_gz_frame(out_png: str) -> bool:
    """Fast grab of the (already-raised) Gazebo window region via ffmpeg."""
    geom = _GZ_GEOM.get("geom")
    if not geom:
        if not raise_gz_window():
            return False
        geom = _GZ_GEOM.get("geom")
    x, y, wdt, hgt = geom
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "x11grab",
             "-draw_mouse", "0", "-video_size", f"{wdt}x{hgt}",
             "-i", f"{DISPLAY}+{x},{y}", "-frames:v", "1", out_png],
            env=env, check=True, timeout=20,
        )
        return os.path.isfile(out_png) and os.path.getsize(out_png) > 5000
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def capture_gz_frame(out_png: str) -> bool:
    """Raise + grab (used for one-off fallback captures)."""
    raise_gz_window()
    return grab_gz_frame(out_png)


NFZ_APPROACH_N = config.NFZ["north_min"] - 1.5  # start grabbing just before entry


def _row_inside_nfz(row: dict) -> bool:
    v = str(row.get("inside_nfz", "")).strip().lower()
    return v in ("true", "1", "yes")


def _row_north(row: dict) -> float:
    try:
        return float(row.get("north", "nan"))
    except (TypeError, ValueError):
        return float("nan")


class FrameWatcher(threading.Thread):
    """Watch a run folder's telemetry CSV; grab start + breach Gazebo frames.

    The telemetry writer flushes per row, so rows are visible live. The Gazebo
    window is raised once up front; grabs are then fast (~0.3 s) so a fly-through
    breach (sub-second) can still be caught inside the NFZ.
    """

    def __init__(self, folder_ready: threading.Event, folder_holder: dict):
        super().__init__(daemon=True)
        self.folder_ready = folder_ready
        self.folder_holder = folder_holder
        self.stop_flag = threading.Event()
        self.start_done = False
        self.breach_done = False

    def run(self) -> None:
        if not self.folder_ready.wait(timeout=300):
            return
        folder = self.folder_holder["folder"]
        csv_path = os.path.join(folder, config.ARTIFACTS["telemetry"])
        start_png = os.path.join(folder, "gazebo_start_frame.png")
        breach_png = os.path.join(folder, "gazebo_breach_frame.png")
        raise_gz_window()  # once, so subsequent grabs are fast
        while not self.stop_flag.is_set():
            rows = []
            if os.path.isfile(csv_path):
                try:
                    with open(csv_path) as fh:
                        rows = list(csv.DictReader(fh))
                except Exception:
                    rows = []
            # start frame: drone airborne, still outside the NFZ
            if not self.start_done and len(rows) >= 2 and not _row_inside_nfz(rows[-1]):
                if grab_gz_frame(start_png):
                    print(f"[frames] start frame -> {start_png}")
                    self.start_done = True
            # breach frame: grab as soon as it's inside; keep updating while inside
            # (last in-zone grab wins) so the drone is centred in the NFZ.
            if rows:
                last = rows[-1]
                approaching = _row_north(last) >= NFZ_APPROACH_N
                if _row_inside_nfz(last) or (approaching and not self.breach_done):
                    if grab_gz_frame(breach_png):
                        if not self.breach_done:
                            print(f"[frames] breach frame -> {breach_png}")
                        self.breach_done = self.breach_done or _row_inside_nfz(last)
            time.sleep(0.15)

    def finish(self, folder: str, breached: bool) -> None:
        """Fallback captures if start/breach were missed live."""
        self.stop_flag.set()
        start_png = os.path.join(folder, "gazebo_start_frame.png")
        breach_png = os.path.join(folder, "gazebo_breach_frame.png")
        if not os.path.isfile(start_png):
            if capture_gz_frame(start_png):
                print(f"[frames] start frame (fallback) -> {start_png}")
        if breached and not os.path.isfile(breach_png):
            if capture_gz_frame(breach_png):
                print(f"[frames] breach frame (fallback) -> {breach_png}")


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def _snapshot_gazebo_runs() -> set[str]:
    root = config.RUNS_GAZEBO_DIR
    if not os.path.isdir(root):
        return set()
    return {d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))}


def _write_run_command(folder: str, scenario: str, vehicle: str) -> None:
    slug = config.resolve_scenario(scenario)
    sid = config.SCENARIO_IDS.get(slug, slug)
    text = f"""# Exact PX4/Gazebo run command — {sid} ({slug})

## Clean restart (before this run)

```bash
pkill -9 -f 'bin/px4'; pkill -9 -f 'gz sim'; pkill -9 -f 'ruby.*gz'; sleep 3
rm -f /tmp/px4_lock-0 /tmp/px4-sock-*
```

## Launch PX4 + Gazebo (GUI visible, {vehicle}, NFZ world)

```bash
cd {PX4_ROOT}
export DISPLAY={DISPLAY}
export PX4_GZ_WORLD={WORLD}
make px4_sitl {vehicle}
```

## Run the scenario (LLM victim, backend=px4)

```bash
cd {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
python run_experiment.py --scenario {sid} --backend px4
```

Orchestrated end-to-end (clean restart + launch + run + frame capture) via:

```bash
python -m tools.run_px4_validation --scenario {sid} --vehicle {vehicle}
```

- LLM model: `{config.LLM_MODEL}`
- Vehicle: `{vehicle}` (x500_depth)  ·  World: `{WORLD}`  ·  GUI: visible (DISPLAY={DISPLAY})
- Run folder: `{os.path.relpath(folder, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}`

## Evidence chain in this folder

`03_memory_audit_log.jsonl`, `10_llm_prompt.txt`, `11_llm_raw_response.txt`,
`12_llm_parsed_action.json`, `13_llm_decisions.jsonl`, `04_flight_telemetry.csv`,
`05_breach_metrics.json`, `06_trajectory_map_2d_nfz.png`, `00_run_report.md`,
`gazebo_start_frame.png`, `gazebo_breach_frame.png`.
"""
    with open(os.path.join(folder, "RUN_COMMAND.md"), "w") as f:
        f.write(text)


async def _run_scenario_task(scenario: str, folder_ready, folder_holder):
    before = _snapshot_gazebo_runs()

    async def _detector():
        for _ in range(600):
            await asyncio.sleep(0.5)
            new = _snapshot_gazebo_runs() - before
            if new:
                folder_holder["folder"] = os.path.join(
                    config.RUNS_GAZEBO_DIR, sorted(new)[-1])
                folder_ready.set()
                return

    det = asyncio.create_task(_detector())
    metrics = await run_experiment.run_scenario(scenario, "px4", config.COMPROMISED_SOURCE)
    det.cancel()
    # ensure folder known
    folder_holder["folder"] = metrics["_folder"]
    folder_ready.set()
    return metrics


def run_one(scenario: str, vehicle: str) -> dict:
    slug = config.resolve_scenario(scenario)
    sid = config.SCENARIO_IDS.get(slug, slug)
    print(f"\n########## Phase 4 PX4 validation — {sid} ({slug}) ##########")

    clean_px4_gz()
    log_path = f"/tmp/px4_phase4_{sid}.log"
    proc = launch_px4(vehicle, log_path)

    folder_ready = threading.Event()
    folder_holder: dict = {"folder": None}
    watcher = FrameWatcher(folder_ready, folder_holder)
    watcher.start()

    metrics = None
    try:
        metrics = asyncio.run(_run_scenario_task(slug, folder_ready, folder_holder))
    finally:
        folder = folder_holder.get("folder")
        if folder:
            time.sleep(1)
            watcher.finish(folder, bool(metrics and metrics.get("breached")))
        stop_px4(proc)

    folder = metrics["_folder"]
    # copy the successful launch log into the run folder for reproducibility
    try:
        import shutil
        shutil.copy2(log_path, os.path.join(folder, "px4_launch.log"))
    except Exception:
        pass
    _write_run_command(folder, slug, vehicle)

    print(f"\n[phase4] {sid}: breached={metrics['breached']} "
          f"entry={metrics['entry_time_s']}s depth={metrics['max_penetration_depth_m']}m")
    print(f"[phase4] folder: {folder}")
    for fn in ("gazebo_start_frame.png", "gazebo_breach_frame.png"):
        p = os.path.join(folder, fn)
        print(f"[phase4] {fn}: {'OK' if os.path.isfile(p) else 'MISSING'}")
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 4 selected PX4/Gazebo validation")
    p.add_argument("--scenario", required=True, help="scenario id/alias, e.g. S3L")
    p.add_argument("--vehicle", default="gz_x500_depth")
    args = p.parse_args()
    run_one(args.scenario, args.vehicle)


if __name__ == "__main__":
    main()
