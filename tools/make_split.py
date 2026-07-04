"""Build a labeled split-screen: left = Gazebo capture, right = trajectory animation.

The two clips are aligned by their END (both finish on the fly-through / target
reached), and the animation is time-scaled to the mission duration so the two
views progress together. Left/right are scaled to a common height and stacked.

    python3 tools/make_split.py \\
        runs/.../08_gazebo_flight_recording_3d.mp4 \\
        runs/.../07_attack_replay_2d_animation.mp4 \\
        runs/.../04_flight_telemetry.csv \\
        runs/.../09_gazebo_and_map_split_screen.mp4
"""

from __future__ import annotations

import csv
import subprocess
import sys


def probe_duration(path: str) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", path,
    ])
    return float(out.strip())


def mission_duration(csv_path: str) -> float:
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    return float(rows[-1]["t"]) - float(rows[0]["t"]) if rows else 0.0


def main():
    gazebo, anim, csv_path, out = sys.argv[1:5]
    h = 540
    d_mission = mission_duration(csv_path)
    d_anim = probe_duration(anim)
    d_gaz = probe_duration(gazebo)

    # Align by end: take the last (d_mission + pad) seconds of the gazebo capture.
    pad = 2.0
    win = d_mission + pad
    gaz_start = max(0.0, d_gaz - win)
    # Time-scale the animation so it lasts `win` seconds too.
    speed = win / d_anim if d_anim > 0 else 1.0

    ff = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    dt_l = (f"drawtext=fontfile={ff}:text='Gazebo / PX4 SITL':x=20:y=20:"
            f"fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8")
    dt_r = (f"drawtext=fontfile={ff}:text='Trajectory + NFZ':x=20:y=20:"
            f"fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8")
    filt = (
        f"[0:v]trim=start={gaz_start:.3f},setpts=PTS-STARTPTS,"
        f"scale=-2:{h},setsar=1,{dt_l}[l];"
        f"[1:v]setpts={speed:.4f}*PTS,scale=-2:{h},setsar=1,{dt_r}[r];"
        f"[l][r]hstack=inputs=2,format=yuv420p[v]"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", gazebo, "-i", anim,
        "-filter_complex", filt, "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-r", "25", "-t", f"{win:.3f}", out,
    ]
    subprocess.check_call(cmd)
    print(f"[split] {out}  (mission={d_mission:.1f}s, window={win:.1f}s, "
          f"anim x{speed:.2f})")


if __name__ == "__main__":
    main()
