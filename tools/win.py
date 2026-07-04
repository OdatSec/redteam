"""Raise / move / resize an X11 window by title substring (for screen recording).

Usage: python3 tools/win.py "Gazebo Sim" X Y W H
"""
import sys
from ewmh import EWMH


def main():
    name_sub = sys.argv[1]
    x, y, w, h = (int(v) for v in sys.argv[2:6])
    e = EWMH()
    wins = e.getClientList() or []
    target = None
    for win in wins:
        try:
            nm = e.getWmName(win)
            nm = nm.decode() if isinstance(nm, bytes) else (nm or "")
        except Exception:
            nm = ""
        if name_sub.lower() in nm.lower():
            target = win
            break
    if target is None:
        print(f"window matching '{name_sub}' not found; clients: "
              f"{[e.getWmName(w) for w in wins]}")
        sys.exit(1)
    # Un-maximize, move/resize, raise, focus.
    try:
        e.setWmState(target, 0, '_NET_WM_STATE_MAXIMIZED_HORZ', '_NET_WM_STATE_MAXIMIZED_VERT')
    except Exception:
        pass
    e.setMoveResizeWindow(target, x=x, y=y, w=w, h=h)
    e.setActiveWindow(target)
    e.display.flush()
    print(f"positioned '{name_sub}' -> {w}x{h}+{x}+{y}")


if __name__ == "__main__":
    main()
