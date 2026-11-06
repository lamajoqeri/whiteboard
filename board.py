#!/usr/bin/env python3
"""Render .whiteboard/ items side by side: text items as-is, .mmd via mermaid-ascii."""
import signal, subprocess, sys, time
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
    # Build the whole frame first, then overwrite in place (home, clear each line's tail,
    # clear below) in one write: no blank-screen flash between frames.
    frame = side_by_side([render(p) for p in items()])
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