"""Plot an attack trajectory over the NFZ from a victim-agent CSV log.

Renders the canonical red-team figure:
    red rectangle = NFZ
    blue line     = drone path (segment colour deepens where poisoned)
    green dot     = start
    black star    = poisoned target
    red X         = first NFZ breach point

    python -m tools.plot_trajectory --log logs/baseline_attack.csv \
        --out plots/baseline_attack_trajectory.png
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


def load(log_path: str) -> list[dict]:
    with open(log_path, "r") as f:
        return list(csv.DictReader(f))


def draw_on_ax(ax, rows: list[dict], title: str | None = None,
               legend: bool = True) -> None:
    """Draw one trajectory (NFZ + benign/poisoned path + markers) onto `ax`.

    Shared by the single-figure `plot()` and the multi-panel contact sheet so both
    render identically.
    """
    north = [float(r["north"]) for r in rows]
    east = [float(r["east"]) for r in rows]
    poisoned = [str(r.get("poisoned", "False")).lower() == "true" for r in rows]

    nfz = config.NFZ
    ax.add_patch(Rectangle(
        (nfz["east_min"], nfz["north_min"]),
        nfz["east_max"] - nfz["east_min"],
        nfz["north_max"] - nfz["north_min"],
        facecolor="red", alpha=0.15, edgecolor="red", linewidth=2, zorder=1,
        label="No-Fly-Zone",
    ))

    # Path split into pre-attack (benign) and post-attack (poisoned) segments.
    def seg(mask, color, label):
        xs = [east[i] for i in range(len(rows)) if mask(i)]
        ys = [north[i] for i in range(len(rows)) if mask(i)]
        if xs:
            ax.plot(xs, ys, "-", color=color, linewidth=2.2, zorder=3, label=label)

    seg(lambda i: not poisoned[i], "#1f77b4", "path (benign command)")
    seg(lambda i: poisoned[i], "#d62728", "path (poisoned command)")
    # thin connector so the full path is continuous
    ax.plot(east, north, "-", color="0.6", linewidth=0.6, zorder=2)

    ax.plot(east[0], north[0], "o", color="green", markersize=12,
            zorder=5, label="start")

    # Poisoned target (last row's target, if any poison happened).
    tgt_rows = [r for r in rows if str(r.get("poisoned", "")).lower() == "true"]
    if tgt_rows:
        tr = tgt_rows[-1]
        ax.plot(float(tr["target_east"]), float(tr["target_north"]), "*",
                color="black", markersize=22, zorder=6, label="poisoned target")

    # First breach point.
    breach = next((r for r in rows if str(r["inside_nfz"]).lower() == "true"), None)
    if breach:
        ax.plot(float(breach["east"]), float(breach["north"]), "X",
                color="red", markersize=16, markeredgecolor="black",
                zorder=7, label=f"breach @ t={float(breach['t']):.2f}s")

    ax.set_xlabel("EAST (m)")
    ax.set_ylabel("NORTH (m)")
    ax.set_title(title or "Baseline memory-poisoning attack: UAV trajectory vs NFZ")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    if legend:
        ax.legend(loc="upper left", fontsize=9)

    all_n = north + [nfz["north_min"], nfz["north_max"]]
    all_e = east + [nfz["east_min"], nfz["east_max"]]
    pad = 2.0
    ax.set_xlim(min(all_e) - pad, max(all_e) + pad)
    ax.set_ylim(min(all_n) - pad, max(all_n) + pad)


def plot(log_path: str, out_path: str, title: str | None = None) -> str:
    rows = load(log_path)
    if not rows:
        raise ValueError(f"empty log: {log_path}")
    fig, ax = plt.subplots(figsize=(8, 8))
    draw_on_ax(ax, rows, title=title)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot] saved {out_path}")
    return out_path


def contact_sheet(entries: list[tuple[str, str]], out_path: str,
                  suptitle: str | None = None) -> str:
    """Compose a grid of trajectory panels. `entries` = [(title, csv_path), ...]."""
    n = len(entries)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 6 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax, (title, csv_path) in zip(axes, entries):
        try:
            draw_on_ax(ax, load(csv_path), title=title, legend=False)
        except Exception as err:  # pragma: no cover
            ax.set_title(f"{title}\n(error: {err})")
    for ax in axes[n:]:
        ax.axis("off")
    # One shared legend, aggregated across every panel so it includes markers
    # (poisoned path / target / breach) that don't appear in the clean panel.
    merged: dict[str, object] = {}
    for ax in axes[:n]:
        for h, lab in zip(*ax.get_legend_handles_labels()):
            if lab.startswith("breach @"):
                lab = "first breach"      # collapse per-panel timestamps
            merged.setdefault(lab, h)
    if merged:
        fig.legend(list(merged.values()), list(merged.keys()),
                   loc="lower center", ncol=len(merged), fontsize=11)
    fig.suptitle(suptitle or "Red-team attack scenarios — trajectory contact sheet",
                 fontsize=16)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.tight_layout(rect=[0, 0.05, 1, 0.97])
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"[contact-sheet] saved {out_path}")
    return out_path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Plot attack trajectory over the NFZ.")
    p.add_argument("--log", default=os.path.join(config.LOGS_DIR, "baseline_attack.csv"))
    p.add_argument("--out", default=os.path.join(config.PLOTS_DIR, "baseline_attack_trajectory.png"))
    p.add_argument("--title", default=None)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    plot(args.log, args.out, args.title)


if __name__ == "__main__":
    main()
