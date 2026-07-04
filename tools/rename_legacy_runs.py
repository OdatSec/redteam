"""One-time helper: rename old run folders and files to the new readable scheme.

    python3 tools/rename_legacy_runs.py          # dry-run (print only)
    python3 tools/rename_legacy_runs.py --apply  # actually rename

Old folder:  runtime_behind_20260703_030942
New folder:  04_runtime_poison_behind_nfz__px4__20260703_030942  (backend from metrics.json)

Old files inside each run are also renamed to the numbered ARTIFACTS names in config.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OLD_SCENARIO_MAP = {
    "clean": "01_clean_mission",
    "static_inside": "02_static_poison_inside_nfz",
    "runtime_inside": "03_runtime_poison_inside_nfz",
    "runtime_behind": "04_runtime_poison_behind_nfz",
    "stealth_drift": "05_stealth_drift_through_nfz",
}

OLD_FILE_MAP = {
    "report.md": config.ARTIFACTS["report"],
    "config_used.json": config.ARTIFACTS["config"],
    "shared_memory_final.json": config.ARTIFACTS["memory_final"],
    "memory_log.jsonl": config.ARTIFACTS["memory_log"],
    "trajectory.csv": config.ARTIFACTS["telemetry"],
    "metrics.json": config.ARTIFACTS["metrics"],
    "trajectory_plot.png": config.ARTIFACTS["map_2d"],
    "attack_animation.mp4": config.ARTIFACTS["replay_2d"],
    "gazebo_capture.mp4": config.ARTIFACTS["gazebo_3d"],
    "split_screen.mp4": config.ARTIFACTS["split_screen"],
}

BATCH_OLD = {
    "SUMMARY.md": config.BATCH_SUMMARY_MD,
    "SUMMARY.png": config.BATCH_CONTACT_SHEET,
}


def _parse_old_folder(name: str) -> tuple[str, str] | None:
    """Return (scenario_slug, timestamp) or None if already new format."""
    if "__" in name and name[:2].isdigit():
        return None  # already new format
    for old, new in OLD_SCENARIO_MAP.items():
        prefix = f"{old}_"
        if name.startswith(prefix):
            return new, name[len(prefix):]
    return None


def _backend_for(folder: str) -> str:
    metrics_path = os.path.join(folder, "metrics.json")
    new_metrics = os.path.join(folder, config.ARTIFACTS["metrics"])
    for p in (metrics_path, new_metrics):
        if os.path.isfile(p):
            try:
                return json.load(open(p)).get("backend", "sim")
            except Exception:
                pass
    return "sim"


def main(apply: bool = False) -> None:
    runs = config.RUNS_DIR
    if not os.path.isdir(runs):
        print("no runs/ directory")
        return

    for old_batch, new_batch in BATCH_OLD.items():
        src = os.path.join(runs, old_batch)
        dst = os.path.join(runs, new_batch)
        if os.path.isfile(src) and not os.path.exists(dst):
            print(f"batch: {old_batch} -> {new_batch}")
            if apply:
                os.rename(src, dst)

    for name in sorted(os.listdir(runs)):
        path = os.path.join(runs, name)
        if not os.path.isdir(path):
            continue
        parsed = _parse_old_folder(name)
        if parsed is None:
            continue
        slug, stamp = parsed
        backend = _backend_for(path)
        new_name = config.run_folder_name(slug, backend, stamp)
        new_path = os.path.join(runs, new_name)
        if name != new_name:
            print(f"folder: {name}\n     -> {new_name}")
            if apply and not os.path.exists(new_path):
                os.rename(path, new_path)
            path = new_path

        for old_file, new_file in OLD_FILE_MAP.items():
            src = os.path.join(path, old_file)
            dst = os.path.join(path, new_file)
            if os.path.isfile(src) and not os.path.exists(dst):
                print(f"  file: {old_file} -> {new_file}")
                if apply:
                    os.rename(src, dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    main(apply=args.apply)
