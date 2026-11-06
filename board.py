#!/usr/bin/env python3
"""Render .whiteboard/ items in wrapping rows: text items as-is, .mmd via mermaid-ascii."""
import shutil, signal, subprocess, sys, time
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).parent
ARGS = [a for a in sys.argv[1:] if a != "--watch"]
BOARD = Path(ARGS[0]) if ARGS else HERE / ".whiteboard"
GAP = "   │   "
RESIZE_SETTLE = 0.2  # seconds without a resize signal before redrawing (tmux sends them ~250ms apart mid-drag)


def render(item):
    if item.suffix == ".mmd":
        out = subprocess.run([HERE / "bin/mermaid-ascii", "-f", item, "-y", "2", "-p", "0"],
                             capture_output=True, text=True).stdout
        return [l.rstrip() for l in out.splitlines()]
    return item.read_text().splitlines()


# ponytail: len() counts every char as 1 column; emoji/CJK are 2 and will overrun slightly
Cell = namedtuple("Cell", "lines width height")


def cell(lines):
    return Cell(lines, max((len(l) for l in lines), default=0), len(lines))


def join_row(cells):
    """Join one row's cells left to right, each padded to its width."""
    rows = []
    for i in range(max((c.height for c in cells), default=0)):
        parts = [(c.lines[i] if i < c.height else "").ljust(c.width) for c in cells]
        rows.append(GAP.join(parts).rstrip())
    return rows


def layout(cells, width, height):
    """Place cells in order, wrapping to a new row when the next one won't fit; crop to width x height."""
    rows, row, used = [], [], 0
    for c in cells:
        need = c.width + (len(GAP) if row else 0)
        if row and used + need > width:  # doesn't fit: start a new row
            rows.append(row)
            row, used, need = [], 0, c.width
        row.append(c)
        used += need
    if row:
        rows.append(row)

    lines = []
    for r in rows:
        if lines:
            lines.append("─" * width)  # rule between rows
        lines += join_row(r)
    return "\n".join(l[:width] for l in lines[:height])


def items():
    return sorted(p for p in BOARD.iterdir() if p.is_file())


def snapshot():
    # name + mtime + size: catches adds, deletes, renames and edits
    return [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in items()]


def draw():
    # Build the whole frame first, then overwrite in place (home, clear each line's tail,
    # clear below) in one write: no blank-screen flash between frames.
    w, h = shutil.get_terminal_size()
    # w - 1: a line filling the last column leaves the cursor in a "pending wrap" state
    # where the clear-to-end-of-line below would erase its final character.
    frame = layout([cell(render(p)) for p in items()], w - 1, h)
    sys.stdout.write("\033[H" + frame.replace("\n", "\033[K\n") + "\033[K\033[J")
    sys.stdout.flush()


resized_at = 0.0  # when the last resize signal arrived; 0 = none pending


def on_resize(*_):
    global resized_at
    resized_at = time.monotonic()


if __name__ == "__main__":
    if "--watch" not in sys.argv:
        draw()
        sys.exit()
    signal.signal(signal.SIGWINCH, on_resize)  # terminal/pane resized, incl. divider drags
    # ponytail: polls mtimes every 0.1s; use fswatch/kqueue if the board grows to many files
    last = None
    while True:
        try:
            now = snapshot()
            # A drag fires many resizes; redraw once they've stopped.
            settled = resized_at and time.monotonic() - resized_at > RESIZE_SETTLE
            if now != last or settled:
                draw()
                last, resized_at = now, 0.0
        except FileNotFoundError:  # file deleted mid-scan; next poll catches up
            pass
        time.sleep(0.1)