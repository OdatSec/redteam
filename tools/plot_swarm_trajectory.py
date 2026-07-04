"""Plot a whole swarm's trajectories over the NFZ from per-agent telemetry CSVs.

Renders one figure with every victim drone's path, the red NFZ prism footprint,
each drone's start dot, and an X at each drone's first breach point.

    python -m tools.plot_swarm_trajectory --run runs/swarm/sw1_..._20260704 \
        --out runs/swarm/sw1_..._20260704/04_swarm_trajectory_map_2d_nfz.png
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
from matplotlib.patches import Rectangle  # noqa: E402

AGENT_COLORS = {"A1": "#1f77b4", "A2": "#2ca02c", "A3": "#9467bd"}


def _load(path: str) -> list[dict]:
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def plot_swarm(run_dir: str, out_path: str, title: str | None = None) -> str:
    nfz = config.NFZ
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.add_patch(Rectangle(
        (nfz["east_min"], nfz["north_min"]),
        nfz["east_max"] - nfz["east_min"],
        nfz["north_max"] - nfz["north_min"],
        facecolor="red", alpha=0.15, edgecolor="red", linewidth=2, zorder=1,
        label="No-Fly-Zone",
    ))

    all_n: list[float] = [nfz["north_min"], nfz["north_max"]]
    all_e: list[float] = [nfz["east_min"], nfz["east_max"]]

    for aid in config.SWARM_VICTIMS:
        csv_path = os.path.join(run_dir, config.swarm_agent_artifacts(aid)["telemetry"])
        if not os.path.exists(csv_path):
            continue
        rows = _load(csv_path)
        if not rows:
            continue
        north = [float(r["north"]) for r in rows]
        east = [float(r["east"]) for r in rows]
        all_n += north
        all_e += east
        color = AGENT_COLORS.get(aid, None)
        ax.plot(east, north, "-", color=color, linewidth=2.0, zorder=3, label=f"{aid} path")
        ax.plot(east[0], north[0], "o", color=color, markersize=11,
                markeredgecolor="black", zorder=5)
        breach = next((r for r in rows if str(r["inside_nfz"]).lower() == "true"), None)
        if breach:
            ax.plot(float(breach["east"]), float(breach["north"]), "X",
                    color=color, markersize=15, markeredgecolor="black", zorder=7,
                    label=f"{aid} breach @ t={float(breach['t']):.1f}s")

    ax.set_xlabel("EAST (m)")
    ax.set_ylabel("NORTH (m)")
    ax.set_title(title or "Swarm trajectories vs No-Fly-Zone")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="upper left", fontsize=9)
    pad = 2.0
    ax.set_xlim(min(all_e) - pad, max(all_e) + pad)
    ax.set_ylim(min(all_n) - pad, max(all_n) + pad)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[swarm-plot] saved {out_path}")
    return out_path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Plot swarm trajectories over the NFZ.")
    p.add_argument("--run", required=True, help="swarm run folder")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default=None)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    out = args.out or os.path.join(args.run, config.SWARM_ARTIFACTS["map_2d"])
    plot_swarm(args.run, out, args.title)


if __name__ == "__main__":
    main()
