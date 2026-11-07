#!/usr/bin/env python3
"""Render .whiteboard/ items in wrapping rows: text items as-is, .mmd via mermaid-ascii."""
import os, select, shutil, signal, subprocess, sys, termios, time, tty
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).parent
ARGS = [a for a in sys.argv[1:] if a != "--watch"]
BOARD = Path(ARGS[0]) if ARGS else HERE / ".whiteboard"
GAP = "   │   "
SCROLL_STEP = 3  # lines per mouse wheel tick
MOUSE_ON, MOUSE_OFF = "\033[?1000h\033[?1006h", "\033[?1000l\033[?1006l"  # button events, SGR encoding
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


def layout(cells, width):
    """Place cells in order, wrapping to a new row when the next one won't fit; crop to width.
    Returns every line: the vertical crop is the scroll window, applied in show()."""
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
    return [l[:width] for l in lines]


def clamp(offset, total, height):
    """Keep the scroll offset between the top and the point where the last line hits the bottom."""
    return max(0, min(offset, total - height))


def items():
    return sorted(p for p in BOARD.iterdir() if p.is_file())


def snapshot():
    # name + mtime + size: catches adds, deletes, renames and edits
    return [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in items()]


lines = []  # the full laid-out board, rebuilt only when files or the pane size change
offset = 0  # how many lines the board is scrolled down


def build():
    global lines
    # w - 1: a line filling the last column leaves the cursor in a "pending wrap" state
    # where the clear-to-end-of-line in show() would erase its final character.
    lines = layout([cell(render(p)) for p in items()], shutil.get_terminal_size().columns - 1)


def show():
    """Write the visible window of the board. Cheap: no rendering, so scrolling can call it per tick."""
    global offset
    h = shutil.get_terminal_size().lines
    offset = clamp(offset, len(lines), h)
    # One write that overwrites in place (home, clear each line's tail, clear below): no flicker.
    frame = "\n".join(lines[offset:offset + h])
    sys.stdout.write("\033[H" + frame.replace("\n", "\033[K\n") + "\033[K\033[J")
    sys.stdout.flush()


def scroll_ticks(data):
    """Net wheel ticks in a chunk of SGR mouse input: down (button 65) is +1, up (64) is -1."""
    return data.count("\033[<65;") - data.count("\033[<64;")


resized_at = 0.0  # when the last resize signal arrived; 0 = none pending


def on_resize(*_):
    global resized_at
    resized_at = time.monotonic()


def watch():
    global offset, resized_at
    signal.signal(signal.SIGWINCH, on_resize)  # terminal/pane resized, incl. divider drags
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # read input as it arrives, without echoing it
    sys.stdout.write(MOUSE_ON)  # ask for wheel events; tmux then forwards them instead of entering copy mode
    try:
        # ponytail: polls mtimes every 0.1s; use fswatch/kqueue if the board grows to many files
        last = None
        while True:
            if select.select([fd], [], [], 0.1)[0]:  # wait up to 0.1s for mouse input
                ticks = scroll_ticks(os.read(fd, 1024).decode(errors="ignore"))
                if ticks:
                    offset += ticks * SCROLL_STEP
                    show()
            try:
                now = snapshot()
                # A drag fires many resizes; redraw once they've stopped.
                settled = resized_at and time.monotonic() - resized_at > RESIZE_SETTLE
                if now != last or settled:
                    build()
                    show()
                    last, resized_at = now, 0.0
            except FileNotFoundError:  # file deleted mid-scan; next poll catches up
                pass
    finally:  # always hand the terminal back: mouse reporting off, normal input mode
        sys.stdout.write(MOUSE_OFF)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


if __name__ == "__main__":
    if "--watch" not in sys.argv:
        build()
        show()
        sys.exit()
    for sig in (signal.SIGTERM, signal.SIGHUP):  # pane killed/closed: exit via finally, not abruptly
        signal.signal(sig, lambda *_: sys.exit())
    try:
        watch()
    except KeyboardInterrupt:
        pass
