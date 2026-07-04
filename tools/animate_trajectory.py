"""Animate an attack trajectory over the NFZ from a victim-agent CSV log.

Produces a presentation-quality clip that plays the episode back frame-by-frame:
    transparent red rectangle = NFZ
    green dot                 = start
    blue path                 = flight under the benign command
    red path                  = flight under the poisoned command
    black star                = poisoned target
    red X                     = first NFZ breach
    on-screen HUD             = clock, injected source (A0), injection time, status

Writes .mp4 when ffmpeg is available, otherwise falls back to .gif (pillow).

    python -m tools.animate_trajectory --log logs/behind_attack.csv \
        --out plots/behind_attack.mp4 --injection-time 8.0
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.animation as manim  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402


def load(log_path: str) -> list[dict]:
    with open(log_path, "r") as f:
        return list(csv.DictReader(f))


def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def _pick_writer(out_path: str):
    """Return (writer, resolved_out_path). Prefer mp4/ffmpeg, else gif/pillow."""
    base, ext = os.path.splitext(out_path)
    if manim.writers.is_available("ffmpeg"):
        return manim.FFMpegWriter(fps=20, bitrate=2400), base + ".mp4"
    return manim.PillowWriter(fps=15), base + ".gif"


def animate(
    log_path: str,
    out_path: str,
    injection_time: float | None = None,
    source: str = config.COMPROMISED_SOURCE,
    title: str | None = None,
    max_frames: int = 160,
) -> str:
    rows = load(log_path)
    if not rows:
        raise ValueError(f"empty log: {log_path}")

    t = [float(r["t"]) for r in rows]
    north = [float(r["north"]) for r in rows]
    east = [float(r["east"]) for r in rows]
    poisoned = [_truthy(r.get("poisoned", "False")) for r in rows]
    inside = [_truthy(r.get("inside_nfz", "False")) for r in rows]
    tgt_n = [float(r.get("target_north", "nan") or "nan") for r in rows]
    tgt_e = [float(r.get("target_east", "nan") or "nan") for r in rows]

    # First breach index (for the red X).
    breach_idx = next((i for i, v in enumerate(inside) if v), None)

    # Subsample frames for a compact, smooth clip.
    n = len(rows)
    step = max(1, n // max_frames)
    frames = list(range(0, n, step))
    if frames[-1] != n - 1:
        frames.append(n - 1)

    nfz = config.NFZ
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.add_patch(Rectangle(
        (nfz["east_min"], nfz["north_min"]),
        nfz["east_max"] - nfz["east_min"],
        nfz["north_max"] - nfz["north_min"],
        facecolor="red", alpha=0.15, edgecolor="red", linewidth=2, zorder=1,
        label="No-Fly-Zone",
    ))

    benign_line, = ax.plot([], [], "-", color="#1f77b4", linewidth=2.4,
                           zorder=3, label="benign path")
    poison_line, = ax.plot([], [], "-", color="#d62728", linewidth=2.4,
                           zorder=3, label="poisoned path")
    head, = ax.plot([], [], "o", color="black", markersize=7, zorder=6)
    ax.plot(east[0], north[0], "o", color="green", markersize=13, zorder=5,
            label="start")
    target_star, = ax.plot([], [], "*", color="black", markersize=22, zorder=6,
                           label="poisoned target")
    breach_x, = ax.plot([], [], "X", color="red", markersize=16,
                        markeredgecolor="black", zorder=7, label="first breach")

    all_n = north + [nfz["north_min"], nfz["north_max"]]
    all_e = east + [nfz["east_min"], nfz["east_max"]]
    pad = 2.0
    ax.set_xlim(min(all_e) - pad, max(all_e) + pad)
    ax.set_ylim(min(all_n) - pad, max(all_n) + pad)
    ax.set_xlabel("EAST (m)")
    ax.set_ylabel("NORTH (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_title(title or "Memory-poisoning attack: UAV trajectory vs NFZ")
    ax.legend(loc="upper left", fontsize=9)

    hud = ax.text(0.98, 0.02, "", transform=ax.transAxes, ha="right", va="bottom",
                  fontsize=10, family="monospace",
                  bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))
    inj_txt = f"{injection_time:.1f}s" if injection_time is not None else "n/a"

    def update(i):
        benign_x = [east[k] for k in range(i + 1) if not poisoned[k]]
        benign_y = [north[k] for k in range(i + 1) if not poisoned[k]]
        poison_x = [east[k] for k in range(i + 1) if poisoned[k]]
        poison_y = [north[k] for k in range(i + 1) if poisoned[k]]
        benign_line.set_data(benign_x, benign_y)
        poison_line.set_data(poison_x, poison_y)
        head.set_data([east[i]], [north[i]])

        if poisoned[i] and tgt_n[i] == tgt_n[i]:  # not NaN
            target_star.set_data([tgt_e[i]], [tgt_n[i]])
        else:
            target_star.set_data([], [])

        if breach_idx is not None and i >= breach_idx:
            breach_x.set_data([east[breach_idx]], [north[breach_idx]])

        status = "INSIDE NFZ" if inside[i] else "outside"
        attacked = injection_time is not None and t[i] >= injection_time
        phase = f"POISONED by {source}" if attacked else "benign mission"
        hud.set_text(
            f"t = {t[i]:5.2f} s\n"
            f"injection @ {inj_txt}  src={source}\n"
            f"phase: {phase}\n"
            f"status: {status}"
        )
        return (benign_line, poison_line, head, target_star, breach_x, hud)

    anim = manim.FuncAnimation(fig, update, frames=frames, blit=True, interval=60)

    writer, out_path = _pick_writer(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"[animate] saved {out_path}")
    return out_path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Animate attack trajectory over the NFZ.")
    p.add_argument("--log", default=os.path.join(config.LOGS_DIR, "baseline_attack.csv"))
    p.add_argument("--out", default=os.path.join(config.PLOTS_DIR, "baseline_attack.mp4"))
    p.add_argument("--injection-time", type=float, default=None)
    p.add_argument("--source", default=config.COMPROMISED_SOURCE)
    p.add_argument("--title", default=None)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    animate(args.log, args.out, args.injection_time, args.source, args.title)


if __name__ == "__main__":
    main()
