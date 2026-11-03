#!/usr/bin/env python3
"""Render .whiteboard/ items side by side: text items as-is, .mmd via mermaid-ascii."""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
BOARD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / ".whiteboard"
GAP = "   │   "


def render(item):
    if item.suffix == ".mmd":
        out = subprocess.run([HERE / "bin/mermaid-ascii", "-f", item, "-y", "2", "-p", "0"],
                             capture_output=True, text=True).stdout
        return [l.rstrip() for l in out.splitlines()]
    return item.read_text().splitlines()


def side_by_side(columns):
    widths = [max((len(l) for l in c), default=0) for c in columns]
    height = max(len(c) for c in columns)
    rows = []
    for i in range(height):
        cells = [(c[i] if i < len(c) else "").ljust(w) for c, w in zip(columns, widths)]
        rows.append(GAP.join(cells).rstrip())
    return "\n".join(rows)


if __name__ == "__main__":
    items = sorted(p for p in BOARD.iterdir() if p.is_file())
    print(side_by_side([render(p) for p in items]))
