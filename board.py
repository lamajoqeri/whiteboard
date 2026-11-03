#!/usr/bin/env python3
"""Render .whiteboard/ items side by side: text items as-is, .mmd via mermaid-ascii."""
import subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).parent
ARGS = [a for a in sys.argv[1:] if a != "--watch"]
BOARD = Path(ARGS[0]) if ARGS else HERE / ".whiteboard"
GAP = "   │   "


def render(item):
    if item.suffix == ".mmd":
        out = subprocess.run([HERE / "bin/mermaid-ascii", "-f", item, "-y", "2", "-p", "0"],
                             capture_output=True, text=True).stdout
        return [l.rstrip() for l in out.splitlines()]
    return item.read_text().splitlines()


def side_by_side(columns):
    widths = [max((len(l) for l in c), default=0) for c in columns]
    height = max((len(c) for c in columns), default=0)
    rows = []
    for i in range(height):
        cells = [(c[i] if i < len(c) else "").ljust(w) for c, w in zip(columns, widths)]
        rows.append(GAP.join(cells).rstrip())
    return "\n".join(rows)


def items():
    return sorted(p for p in BOARD.iterdir() if p.is_file())


def snapshot():
    # name + mtime + size: catches adds, deletes, renames and edits
    return [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in items()]


def draw():
    print("\033[H\033[2J" + side_by_side([render(p) for p in items()]), flush=True)


if __name__ == "__main__":
    if "--watch" not in sys.argv:
        draw()
        sys.exit()
    # ponytail: polls mtimes once a second; use fswatch/kqueue if instant updates matter
    last = None
    while True:
        try:
            now = snapshot()
            if now != last:
                draw()
                last = now
        except FileNotFoundError:  # file deleted mid-scan; next poll catches up
            pass
        time.sleep(1)