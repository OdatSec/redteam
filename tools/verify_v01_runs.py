"""Verify RedTeam v0.1 run folders contain required artifacts and metadata."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

REQUIRED_FILES = [
    config.ARTIFACTS["report"],
    config.ARTIFACTS["config"],
    config.ARTIFACTS["memory_final"],
    config.ARTIFACTS["memory_log"],
    config.ARTIFACTS["telemetry"],
    config.ARTIFACTS["metrics"],
    config.ARTIFACTS["map_2d"],
    config.ARTIFACTS["replay_2d"],
]

REQUIRED_METRICS = [
    "benchmark", "benchmark_version", "scenario_id", "backend", "breached",
]


def verify_run(folder: str) -> list[str]:
    errors = []
    for fname in REQUIRED_FILES:
        p = os.path.join(folder, fname)
        if not os.path.isfile(p):
            errors.append(f"missing: {fname}")
        elif os.path.getsize(p) == 0:
            errors.append(f"empty: {fname}")

    mp = os.path.join(folder, config.ARTIFACTS["metrics"])
    if os.path.isfile(mp):
        try:
            m = json.load(open(mp))
            if m.get("benchmark") != config.BENCHMARK_FULL:
                errors.append(f"benchmark != {config.BENCHMARK_FULL!r}")
            if m.get("benchmark_version") != config.BENCHMARK_VERSION:
                errors.append(f"benchmark_version != {config.BENCHMARK_VERSION!r}")
            sid = m.get("scenario_id")
            if sid not in ("S0", "S1", "S2", "S3", "S4"):
                errors.append(f"invalid scenario_id: {sid!r}")
            for k in REQUIRED_METRICS:
                if k not in m:
                    errors.append(f"metrics missing key: {k}")
        except Exception as e:
            errors.append(f"metrics parse error: {e}")
    return errors


def scan(root: str) -> dict:
    results = {}
    if not os.path.isdir(root):
        return results
    for name in sorted(os.listdir(root)):
        if name.startswith(".") or name.endswith(".md") or name.endswith(".png"):
            continue
        path = os.path.join(root, name)
        if os.path.isdir(path):
            results[name] = verify_run(path)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", default=config.RUNS_SIM_DIR)
    ap.add_argument("--gazebo", default=config.RUNS_GAZEBO_DIR)
    args = ap.parse_args()

    all_ok = True
    for label, root in [("sim", args.sim), ("gazebo", args.gazebo)]:
        print(f"\n=== {label}: {root} ===")
        for folder, errs in scan(root).items():
            if errs:
                all_ok = False
                print(f"FAIL  {folder}")
                for e in errs:
                    print(f"      - {e}")
            else:
                print(f"OK    {folder}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
