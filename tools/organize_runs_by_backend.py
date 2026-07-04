"""Move existing run folders into runs/sim/ and runs/gazebo/.

    python3 tools/organize_runs_by_backend.py          # dry-run
    python3 tools/organize_runs_by_backend.py --apply  # move folders
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SKIP = {"sim", "gazebo", "README.md"}
BATCH_FILES = {config.BATCH_SUMMARY_MD, config.BATCH_CONTACT_SHEET}


def _backend_from_name(name: str) -> str | None:
    if "__px4__" in name:
        return "px4"
    if "__sim__" in name:
        return "sim"
    return None


def _backend_from_metrics(folder: str) -> str:
    for fname in (config.ARTIFACTS["metrics"], "metrics.json", "05_breach_metrics.json"):
        p = os.path.join(folder, fname)
        if os.path.isfile(p):
            try:
                return json.load(open(p)).get("backend", "sim")
            except Exception:
                pass
    return "sim"


def _clean_folder_name(name: str) -> str:
    """Strip embedded __sim__ / __px4__ from folder name."""
    name = re.sub(r"__px4__", "__", name)
    name = re.sub(r"__sim__", "__", name)
    return name


def main(apply: bool = False) -> None:
    for sub in (config.RUNS_SIM_DIR, config.RUNS_GAZEBO_DIR):
        os.makedirs(sub, exist_ok=True)

    # Move batch summaries at runs/ root into sim/ if they exist (legacy).
    for batch in BATCH_FILES:
        src = os.path.join(config.RUNS_DIR, batch)
        if os.path.isfile(src):
            dst = os.path.join(config.RUNS_SIM_DIR, batch)
            print(f"batch (legacy root): {batch} -> sim/{batch}")
            if apply and not os.path.exists(dst):
                shutil.move(src, dst)

    for name in sorted(os.listdir(config.RUNS_DIR)):
        if name in SKIP or name in BATCH_FILES:
            continue
        src = os.path.join(config.RUNS_DIR, name)
        if not os.path.isdir(src):
            continue

        backend = _backend_from_name(name) or _backend_from_metrics(src)
        dest_root = config.runs_dir(backend)
        clean = _clean_folder_name(name)
        dst = os.path.join(dest_root, clean)

        rel = "sim" if backend == "sim" else "gazebo"
        if os.path.normpath(src) == os.path.normpath(dst):
            continue
        print(f"{name}\n  -> {rel}/{clean}")
        if apply:
            os.makedirs(dest_root, exist_ok=True)
            if os.path.exists(dst):
                print(f"  (skip: destination exists)")
            else:
                shutil.move(src, dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(apply=ap.parse_args().apply)
