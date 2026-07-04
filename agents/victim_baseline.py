"""Victim baseline agent -- the vulnerable, no-defense LLM-UAV agent.

This is the drone brain the red team attacks. It BLINDLY TRUSTS shared memory:

    read shared_memory.json  ->  turn the command into an NED target  ->  fly there

Every control tick (~5 Hz) it re-reads memory, so a command injected mid-flight
by the attack launcher is picked up and executed within one tick -- there is NO
NFZ check gating the action (that is the world-model defense's job, added later).
The only place the NFZ appears is in the MEASUREMENT layer (BreachMetrics), which
scores whether the attack succeeded; it never changes the drone's behaviour.

    memory says goto  ->  agent executes   (no world model, no veto)

Usage:
    python -m agents.victim_baseline --backend sim            # offline, no PX4
    python -m agents.victim_baseline --backend px4            # PX4 SITL + Gazebo
    python -m agents.victim_baseline --backend px4 --seed-safe # also seed t=0 cmd

Run the attack launcher (attacks/attack_launcher.py) in parallel to poison memory
during flight.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from agents import memory_bus  # noqa: E402
from agents.backends import make_backend  # noqa: E402
from world_model.nfz_geometry import BreachMetrics, NoFlyZone  # noqa: E402

LOG_FIELDS = [
    "t", "north", "east", "down", "inside_nfz", "clearance",
    "source", "attack_type", "poisoned",
    "target_north", "target_east", "target_down", "trusted_claim",
]


async def run(
    backend_name: str,
    log_path: str,
    seed_safe: bool,
    stop_on_breach: bool,
    after_breach_hold_s: float,
    max_steps: int,
    terminal_target: tuple[float, float] | None = None,
    loop_started: "asyncio.Event | None" = None,
) -> dict:
    nfz = NoFlyZone.from_config(config.NFZ)
    metrics = BreachMetrics(nfz=nfz)

    if seed_safe:
        memory_bus.reset_log()
        memory_bus.seed_safe_command(clock=0.0)

    backend = make_backend(backend_name)
    print(f"[victim] backend={backend_name}  starting flight ...")
    await backend.start()

    # Ensure there is *something* in memory to follow.
    if memory_bus.read_memory() is None:
        memory_bus.seed_safe_command(clock=0.0)

    print("[victim] BASELINE MODE: no world model, no defense.")
    print("[victim] The agent trusts shared memory and executes it directly.\n")

    t0 = time.time()
    # Signal that the control loop is starting (t=0). Attack launchers wait on
    # this so injection timing is measured from post-takeoff loop start, not from
    # task creation -- critical on PX4 where takeoff/settle takes ~15-20 s.
    if loop_started is not None:
        loop_started.set()
    breach_logged_at = None
    breach_deadline = None
    last_source = None

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        writer.writeheader()

        for _ in range(max_steps):
            t = time.time() - t0

            cmd = memory_bus.read_memory()
            if cmd is None:
                await asyncio.sleep(config.CONTROL_DT)
                continue

            # Announce a command source change (e.g. mission_planner -> A0).
            if cmd.source != last_source:
                tag = "  <== POISON" if cmd.poisoned else ""
                print(f"[victim] t={t:5.2f}s  now trusting source={cmd.source} "
                      f"target=({cmd.target_north},{cmd.target_east},{cmd.target_down}){tag}")
                if cmd.trusted_claim:
                    print(f"          claim: \"{cmd.trusted_claim}\"")
                last_source = cmd.source

            # BLIND TRUST: command -> action, no NFZ gate.
            await backend.goto(cmd.target_north, cmd.target_east, cmd.target_down)
            n, e, d = await backend.position()

            inside = metrics.update(t, n, e)
            clearance = nfz.clearance(n, e)
            # The run ends only when the drone reaches its FINAL objective
            # (terminal_target), never at intermediate waypoints -- this keeps a
            # stealth-drift attack (which issues many small nudges) running all the
            # way through the NFZ instead of stopping at the first nudge.
            reached = (
                terminal_target is not None
                and abs(n - terminal_target[0]) < 0.3
                and abs(e - terminal_target[1]) < 0.3
            )

            writer.writerow({
                "t": f"{t:.3f}",
                "north": f"{n:.4f}", "east": f"{e:.4f}", "down": f"{d:.4f}",
                "inside_nfz": inside, "clearance": f"{clearance:.4f}",
                "source": cmd.source, "attack_type": cmd.attack_type,
                "poisoned": cmd.poisoned,
                "target_north": cmd.target_north, "target_east": cmd.target_east,
                "target_down": cmd.target_down, "trusted_claim": cmd.trusted_claim,
            })

            status = "INSIDE NFZ" if inside else "outside"
            print(f"[victim] t={t:5.2f}s  N={n:6.2f} E={e:6.2f} D={d:6.2f}  "
                  f"clr={clearance:6.2f}  {status}")

            if inside and breach_logged_at is None:
                breach_logged_at = t
                print("\n[victim] *** NFZ BREACH *** the baseline agent trusted "
                      f"'{cmd.source}' and entered the NFZ (attack success).\n")
                if stop_on_breach:
                    # Keep flying (and sampling) inside the NFZ for the hold window
                    # so the log/metrics capture real dwell time and penetration
                    # depth instead of stopping at the first breach sample.
                    breach_deadline = t + after_breach_hold_s

            if breach_deadline is not None and t >= breach_deadline:
                print(f"[victim] t={t:5.2f}s  held inside NFZ for "
                      f"{after_breach_hold_s:.1f}s after breach; ending run.")
                break

            if reached:
                print(f"[victim] t={t:5.2f}s  target reached "
                      f"({cmd.target_north},{cmd.target_east}); ending run.")
                break

            await asyncio.sleep(config.CONTROL_DT)

    print("[victim] landing ...")
    await backend.land()

    summary = metrics.summary()
    summary["log"] = log_path
    print("\n[victim] ===== run summary =====")
    for k, v in summary.items():
        print(f"    {k}: {v}")
    return summary


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Victim baseline UAV agent (trusts memory).")
    p.add_argument("--backend", choices=["sim", "px4"], default="sim")
    p.add_argument("--log", default=os.path.join(config.LOGS_DIR, "baseline_attack.csv"))
    p.add_argument("--seed-safe", action="store_true",
                   help="reset the log and seed the benign t=0 command before flying")
    p.add_argument("--no-stop-on-breach", dest="stop_on_breach", action="store_false")
    p.add_argument("--after-breach-hold", dest="after_breach_hold_s", type=float, default=2.5,
                   help="seconds to keep flying inside the NFZ after first breach")
    p.add_argument("--max-steps", type=int, default=config.CONTROL_MAX_STEPS)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return asyncio.run(run(
        backend_name=args.backend,
        log_path=args.log,
        seed_safe=args.seed_safe,
        stop_on_breach=args.stop_on_breach,
        after_breach_hold_s=args.after_breach_hold_s,
        max_steps=args.max_steps,
    ))


if __name__ == "__main__":
    main()
