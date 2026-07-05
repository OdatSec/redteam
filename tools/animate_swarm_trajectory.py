"""Animate a swarm episode (A1/A2/A3) over the NFZ from per-agent telemetry.

Produces one top-down replay per scenario, reconstructed entirely from the
existing per-agent telemetry CSVs (no Gazebo video needed):

    transparent red rectangle = NFZ
    coloured dot per victim    = A1 / A2 / A3 live position
    coloured path per victim   = flight path (dashed = benign, solid = poisoned)
    coloured X per victim       = that victim's first NFZ breach
    on-screen HUD               = scenario label, clock, A0 injection time,
                                  phase (benign vs poisoned), #breached

A0 is the attacker/source: it writes shared memory but does not fly, so it is
shown as a HUD label, not a drone marker.

    python -m tools.animate_swarm_trajectory --run runs/swarm/sw1_..._20260704
    python -m tools.animate_swarm_trajectory --all
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.animation as manim  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

AGENT_COLORS = {"A1": "#1f77b4", "A2": "#2ca02c", "A3": "#9467bd"}

# Output filename per scenario id.
OUT_NAMES = {
    "SW0": "SW0_clean_swarm_replay.mp4",
    "SW1": "SW1_route_lure_swarm_replay.mp4",
    "SW2": "SW2_policy_clearance_swarm_replay.mp4",
    "SW3": "SW3_stealth_drift_swarm_replay.mp4",
}


def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def _load_agent(run_dir: str, aid: str) -> list[dict]:
    path = os.path.join(run_dir, config.swarm_agent_artifacts(aid)["telemetry"])
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _sample_at(rows: list[dict], t: float) -> dict | None:
    """Last telemetry row with time <= t (step-hold), or None before first sample."""
    chosen = None
    for r in rows:
        if float(r["t"]) <= t:
            chosen = r
        else:
            break
    return chosen


def _pick_writer(out_path: str):
    base, _ = os.path.splitext(out_path)
    if manim.writers.is_available("ffmpeg"):
        return manim.FFMpegWriter(fps=20, bitrate=2400), base + ".mp4"
    return manim.PillowWriter(fps=15), base + ".gif"


def _scenario_from_run(run_dir: str) -> tuple[str, str, float | None]:
    """Return (scenario_id, scenario_name, injection_time) from run config."""
    cfg_path = os.path.join(run_dir, config.SWARM_ARTIFACTS["config"])
    cfg = json.load(open(cfg_path))
    return cfg["scenario_id"], cfg["scenario_name"], cfg.get("attack_delay_s")


def animate_run(run_dir: str, out_path: str | None = None,
                max_frames: int = 200) -> str:
    sid, sname, injection = _scenario_from_run(run_dir)
    agents = {aid: _load_agent(run_dir, aid) for aid in config.SWARM_VICTIMS}
    agents = {k: v for k, v in agents.items() if v}
    if not agents:
        raise ValueError(f"no victim telemetry in {run_dir}")

    # Per-agent first-breach time + point.
    breach_pt: dict[str, tuple[float, float, float]] = {}
    for aid, rows in agents.items():
        for r in rows:
            if _truthy(r.get("inside_nfz")):
                breach_pt[aid] = (float(r["t"]), float(r["east"]), float(r["north"]))
                break

    # Fleet first / last breach times (for on-screen markers).
    breach_times = sorted(v[0] for v in breach_pt.values())
    fleet_first_breach = breach_times[0] if breach_times else None
    fleet_last_breach = breach_times[-1] if breach_times else None

    t_max = max(float(rows[-1]["t"]) for rows in agents.values())
    frame_times = [t_max * i / (max_frames - 1) for i in range(max_frames)]

    nfz = config.NFZ
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    ax.add_patch(Rectangle(
        (nfz["east_min"], nfz["north_min"]),
        nfz["east_max"] - nfz["east_min"],
        nfz["north_max"] - nfz["north_min"],
        facecolor="red", alpha=0.15, edgecolor="red", linewidth=2, zorder=1,
        label="No-Fly-Zone",
    ))

    benign_lines, poison_lines, heads, breach_marks, id_labels = {}, {}, {}, {}, {}
    all_n = [nfz["north_min"], nfz["north_max"]]
    all_e = [nfz["east_min"], nfz["east_max"]]
    for aid, rows in agents.items():
        color = AGENT_COLORS.get(aid, "black")
        benign_lines[aid], = ax.plot([], [], "--", color=color, linewidth=1.6,
                                     alpha=0.7, zorder=3)
        poison_lines[aid], = ax.plot([], [], "-", color=color, linewidth=2.6,
                                     zorder=4, label=f"{aid} (victim LLM UAV)")
        heads[aid], = ax.plot([], [], "o", color=color, markersize=11,
                              markeredgecolor="black", zorder=6)
        breach_marks[aid], = ax.plot([], [], "X", color=color, markersize=16,
                                     markeredgecolor="black", zorder=7)
        # Moving drone id label that follows the head.
        id_labels[aid] = ax.text(0, 0, aid, color=color, fontsize=10,
                                 fontweight="bold", ha="left", va="bottom", zorder=8)
        ax.plot(float(rows[0]["east"]), float(rows[0]["north"]), "o", color=color,
                markersize=9, alpha=0.5, zorder=2)
        all_n += [float(r["north"]) for r in rows]
        all_e += [float(r["east"]) for r in rows]

    # NFZ centre label.
    cn = 0.5 * (nfz["north_min"] + nfz["north_max"])
    ce = 0.5 * (nfz["east_min"] + nfz["east_max"])
    ax.text(ce, cn, "NFZ", color="darkred", fontsize=13, fontweight="bold",
            ha="center", va="center", alpha=0.7, zorder=2)

    pad = 2.0
    ax.set_xlim(min(all_e) - pad, max(all_e) + pad)
    ax.set_ylim(min(all_n) - pad, max(all_n) + pad)
    ax.set_xlabel("EAST (m)")
    ax.set_ylabel("NORTH (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"{sid} — {sname}: shared-memory swarm vs NFZ")
    ax.legend(loc="upper left", fontsize=9)

    inj_txt = f"{injection:.1f}s" if injection is not None else "n/a (clean)"
    first_txt = f"{fleet_first_breach:.1f}s" if fleet_first_breach is not None else "—"
    last_txt = f"{fleet_last_breach:.1f}s" if fleet_last_breach is not None else "—"
    hud = ax.text(0.98, 0.02, "", transform=ax.transAxes, ha="right", va="bottom",
                  fontsize=10, family="monospace",
                  bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))
    # A0 attacker/source label (A0 writes memory, it does not fly).
    a0_txt = ax.text(0.02, 0.02, "", transform=ax.transAxes, ha="left", va="bottom",
                     fontsize=9, family="monospace",
                     bbox=dict(boxstyle="round", facecolor="#ffecec", alpha=0.9))

    def update(fi):
        t = frame_times[fi]
        n_breached = 0
        artists = []
        for aid, rows in agents.items():
            upto = [r for r in rows if float(r["t"]) <= t]
            bx = [float(r["east"]) for r in upto if not _truthy(r.get("poisoned"))]
            by = [float(r["north"]) for r in upto if not _truthy(r.get("poisoned"))]
            px = [float(r["east"]) for r in upto if _truthy(r.get("poisoned"))]
            py = [float(r["north"]) for r in upto if _truthy(r.get("poisoned"))]
            benign_lines[aid].set_data(bx, by)
            poison_lines[aid].set_data(px, py)
            cur = _sample_at(rows, t) or rows[0]
            ce_, cn_ = float(cur["east"]), float(cur["north"])
            heads[aid].set_data([ce_], [cn_])
            id_labels[aid].set_position((ce_ + 0.15, cn_ + 0.15))
            if aid in breach_pt and t >= breach_pt[aid][0]:
                breach_marks[aid].set_data([breach_pt[aid][1]], [breach_pt[aid][2]])
                n_breached += 1
            artists += [benign_lines[aid], poison_lines[aid], heads[aid],
                        breach_marks[aid], id_labels[aid]]

        attacked = injection is not None and t >= injection
        phase = "POISONED (A0 broadcast)" if attacked else "benign mission"
        fb = f"{fleet_first_breach:.1f}s" if (fleet_first_breach is not None and t >= fleet_first_breach) else "—"
        lb = f"{fleet_last_breach:.1f}s" if (fleet_last_breach is not None and t >= fleet_last_breach) else "—"
        hud.set_text(
            f"scenario: {sid}\n"
            f"t = {t:5.2f} s / {t_max:.1f} s\n"
            f"A0 injection @ {inj_txt}\n"
            f"phase: {phase}\n"
            f"victims breached: {n_breached}/{len(agents)}\n"
            f"first breach: {fb}   last breach: {lb}"
        )
        a0_status = "ACTIVE — poisoning shared memory" if attacked else "idle (pre-injection)"
        a0_txt.set_text(f"A0 = attacker / compromised memory writer\n(source label; does not fly)\nstatus: {a0_status}")
        artists += [hud, a0_txt]
        return artists

    anim = manim.FuncAnimation(fig, update, frames=len(frame_times),
                               blit=True, interval=60)
    if out_path is None:
        out_path = os.path.join(run_dir, OUT_NAMES.get(sid, f"{sid}_swarm_replay.mp4"))
    writer, out_path = _pick_writer(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"[swarm-animate] saved {out_path}")
    return out_path


def _latest_run(sid: str) -> str | None:
    slug = config.SWARM_SCENARIO_IDS[sid]
    matches = sorted(glob.glob(os.path.join(config.RUNS_SWARM_DIR, f"{slug}__*")))
    return matches[-1] if matches else None


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Animate swarm replay from telemetry.")
    p.add_argument("--run", help="swarm run folder")
    p.add_argument("--all", action="store_true", help="latest run for SW0–SW3")
    p.add_argument("--out", default=None)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.all:
        for sid in config.SWARM_SCENARIO_ORDER:
            run = _latest_run(sid)
            if run:
                animate_run(run)
            else:
                print(f"[swarm-animate] no run found for {sid}")
    elif args.run:
        animate_run(args.run, args.out)
    else:
        raise SystemExit("specify --run <folder> or --all")


if __name__ == "__main__":
    main()
