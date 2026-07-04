"""Verify RedTeam v0.2 LLM evaluation QC folder (pre-freeze gate).

Checks runs/sim/llm_eval/ for:
  - exactly 30 trial folders (10 × S2L, 10 × S3L, 10 × S4L)
  - required artifacts in every trial
  - benchmark metadata in every trial metrics JSON
  - llm_action_valid=true, llm_used_poisoned_memory=true, breached=true
  - summary files at eval root

Exit 0 = pass, 1 = fail.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

EVAL_ROOT = os.path.join(config.RUNS_SIM_DIR, "llm_eval")

SCENARIO_PREFIX = {
    "S2L": "06_llm_runtime_poison_inside_nfz",
    "S3L": "07_llm_runtime_poison_behind_nfz",
    "S4L": "08_llm_stealth_drift_through_nfz",
}

TRIALS_PER_SCENARIO = 10
TOTAL_TRIALS = 30

REQUIRED_TRIAL_FILES = [
    config.ARTIFACTS["report"],
    config.ARTIFACTS["memory_log"],
    config.ARTIFACTS["telemetry"],
    config.ARTIFACTS["metrics"],
    config.ARTIFACTS["map_2d"],
    config.ARTIFACTS["replay_2d"],
    config.ARTIFACTS_LLM["prompt"],
    config.ARTIFACTS_LLM["raw"],
    config.ARTIFACTS_LLM["parsed"],
    config.ARTIFACTS_LLM["decisions"],
]

SUMMARY_FILES = [
    "LLM_EVAL_SUMMARY.md",
    "LLM_EVAL_SUMMARY.csv",
    "LLM_EVAL_SUMMARY.json",
    "LLM_EVAL_TRIALS.csv",
]

REQUIRED_METRICS_KEYS = [
    "benchmark", "benchmark_version", "scenario_id", "backend", "breached",
]


def _trial_folders(root: str) -> list[str]:
    """Return sorted trial folder paths (exclude summary files)."""
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path) and "__t" in name:
            out.append(path)
    return out


def _scenario_id(folder_name: str) -> str | None:
    for sid, prefix in SCENARIO_PREFIX.items():
        if folder_name.startswith(prefix):
            return sid
    return None


def verify_trial(folder: str) -> list[str]:
    errors = []
    name = os.path.basename(folder)

    for fname in REQUIRED_TRIAL_FILES:
        p = os.path.join(folder, fname)
        if not os.path.isfile(p):
            errors.append(f"missing: {fname}")
        elif os.path.getsize(p) == 0:
            errors.append(f"empty: {fname}")

    mp = os.path.join(folder, config.ARTIFACTS["metrics"])
    if not os.path.isfile(mp):
        return errors

    try:
        m = json.load(open(mp))
    except Exception as err:
        errors.append(f"metrics parse error: {err}")
        return errors

    for k in REQUIRED_METRICS_KEYS:
        if k not in m:
            errors.append(f"metrics missing key: {k}")

    sid = m.get("scenario_id")
    expected_sid = _scenario_id(name)
    if expected_sid and sid != expected_sid:
        errors.append(f"scenario_id {sid!r} != expected {expected_sid!r}")

    if sid not in SCENARIO_PREFIX:
        errors.append(f"invalid scenario_id: {sid!r}")

    if m.get("backend") != "sim":
        errors.append(f"backend != 'sim' (got {m.get('backend')!r})")

    if m.get("breached") is not True:
        errors.append(f"breached != true (got {m.get('breached')!r})")

    llm = m.get("llm")
    if not isinstance(llm, dict):
        errors.append("metrics missing llm block")
        return errors

    if llm.get("llm_action_valid") is not True:
        errors.append(f"llm_action_valid != true (got {llm.get('llm_action_valid')!r})")

    if llm.get("llm_used_poisoned_memory") is not True:
        errors.append(
            f"llm_used_poisoned_memory != true (got {llm.get('llm_used_poisoned_memory')!r})"
        )

    return errors


def verify_summaries(root: str) -> list[str]:
    errors = []
    for fname in SUMMARY_FILES:
        p = os.path.join(root, fname)
        if not os.path.isfile(p):
            errors.append(f"missing summary: {fname}")
        elif os.path.getsize(p) == 0:
            errors.append(f"empty summary: {fname}")
    return errors


def verify_counts(folders: list[str]) -> list[str]:
    errors = []
    if len(folders) != TOTAL_TRIALS:
        errors.append(f"expected {TOTAL_TRIALS} trial folders, found {len(folders)}")

    by_scenario: dict[str, int] = {sid: 0 for sid in SCENARIO_PREFIX}
    for folder in folders:
        sid = _scenario_id(os.path.basename(folder))
        if sid is None:
            errors.append(f"unrecognized trial folder: {os.path.basename(folder)}")
        else:
            by_scenario[sid] += 1

    for sid, expected in SCENARIO_PREFIX.items():
        got = by_scenario[sid]
        if got != TRIALS_PER_SCENARIO:
            errors.append(f"{sid}: expected {TRIALS_PER_SCENARIO} trials, found {got}")

    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify v0.2 LLM eval QC folder.")
    ap.add_argument("--root", default=EVAL_ROOT)
    args = ap.parse_args(argv)

    root = args.root
    all_errors: list[str] = []
    print(f"\n=== v0.2 LLM eval QC: {root} ===\n")

    if not os.path.isdir(root):
        print(f"FAIL  eval root does not exist: {root}")
        return 1

    folders = _trial_folders(root)
    count_errs = verify_counts(folders)
    if count_errs:
        all_errors.extend(count_errs)
        for e in count_errs:
            print(f"COUNT  {e}")
    else:
        print(f"OK     {len(folders)} trial folders (10 × S2L, 10 × S3L, 10 × S4L)")

    summary_errs = verify_summaries(root)
    if summary_errs:
        all_errors.extend(summary_errs)
        for e in summary_errs:
            print(f"SUMMARY  {e}")
    else:
        print("OK     all summary files present")

    trial_fail = 0
    for folder in folders:
        errs = verify_trial(folder)
        if errs:
            trial_fail += 1
            all_errors.extend(errs)
            print(f"FAIL  {os.path.basename(folder)}")
            for e in errs:
                print(f"      - {e}")
        else:
            print(f"OK    {os.path.basename(folder)}")

    print()
    if all_errors:
        print(f"RESULT: FAIL ({len(all_errors)} issue(s), {trial_fail} trial(s) failed)")
        return 1

    print("RESULT: PASS — all 30 trials verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
