#!/usr/bin/env python3
"""Render .whiteboard/ items in wrapping rows: text items as-is, .mmd via mermaid-ascii."""
import os, re, shutil, signal, subprocess, sys, textwrap, time
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).parent
MERMAID = HERE / "bin" / ("mermaid-ascii.exe" if os.name == "nt" else "mermaid-ascii")  # Windows build is .exe
ARGS = [a for a in sys.argv[1:] if a != "--watch"]
BOARD = Path(ARGS[0]) if ARGS else HERE / ".whiteboard"
GAP = "   │   "
SCROLL_STEP = 3  # lines per mouse wheel tick
MOUSE_ON, MOUSE_OFF = "\033[?1000h\033[?1006h", "\033[?1000l\033[?1006l"  # button events, SGR encoding
RESIZE_SETTLE = 0.2  # seconds without a size change before redrawing (tmux resizes ~250ms apart mid-drag)

# Terminal input, the only part that differs per OS: raw_mode() switches to reading input as it
# arrives without echoing it and returns a function that switches back; wait_input(t) waits up to
# t seconds and returns whatever arrived ("" if nothing).
if os.name == "nt":
    import ctypes, msvcrt
    k32 = ctypes.windll.kernel32

    def raw_mode():
        inp, out = k32.GetStdHandle(-10), k32.GetStdHandle(-11)  # console input, output
        imode, omode = ctypes.c_uint32(), ctypes.c_uint32()
        k32.GetConsoleMode(inp, ctypes.byref(imode))
        k32.GetConsoleMode(out, ctypes.byref(omode))
        # input: line buffering (0x2) and echo (0x4) off; VT input (0x200) on, so the mouse wheel
        # arrives as ESC[<65;... text like on macOS instead of Windows mouse event records
        k32.SetConsoleMode(inp, (imode.value & ~0x6) | 0x200)
        k32.SetConsoleMode(out, omode.value | 0x4)  # output: understand the ESC codes show() writes
        return lambda: (k32.SetConsoleMode(inp, imode.value), k32.SetConsoleMode(out, omode.value))

    def wait_input(timeout):
        # Polls kbhit() rather than waiting on the console handle: that also wakes for focus and
        # key-up events, which carry no text, and reading after it would block.
        end = time.monotonic() + timeout
        while not msvcrt.kbhit():
            if time.monotonic() >= end:
                return ""
            time.sleep(0.01)
        chars = []
        while msvcrt.kbhit():
            chars.append(msvcrt.getwch())
        return "".join(chars)
else:
    import select, termios, tty

    def raw_mode():
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return lambda: termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    def wait_input(timeout):
        fd = sys.stdin.fileno()
        return os.read(fd, 1024).decode(errors="ignore") if select.select([fd], [], [], timeout)[0] else ""


def render(item):
    if item.suffix == ".mmd":
        try:
            run = subprocess.run([MERMAID, "-f", item, "-y", "2", "-p", "0"],
                                 capture_output=True, text=True)
        except OSError:  # bin/ is gitignored, so a fresh clone won't have it
            return [f"{item.name}: mermaid-ascii not installed"]
        if run.returncode:  # bad syntax / unsupported diagram: say why instead of vanishing
            why = re.search(r'msg="(.*)"', run.stderr)  # its log line: level=fatal msg="..."
            return [f"{item.name}: mermaid error"] + textwrap.wrap(why[1] if why else run.stderr, 40)
        return [l.rstrip() for l in run.stdout.splitlines()]
    data = item.read_bytes()
    if b"\0" in data:  # NUL byte = binary (same heuristic git uses): label it instead of printing garbage
        return [f"{item.name}: binary file ({item.suffix[1:] or 'unknown type'})"]
    return data.decode(errors="replace").splitlines()  # odd bytes become �, never a crash


def clean(line):
    """Make a line safe to print: tabs become spaces (len() counts a tab as 1 column, the terminal
    up to 8), and control chars like ESC become � so they show as text instead of recoloring,
    clearing or moving the cursor."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "�", line.expandtabs(4))


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
    # skip hidden files: editor swap files (.x.swp), .DS_Store and other dotfile clutter
    return sorted(p for p in BOARD.iterdir() if p.is_file() and not p.name.startswith("."))


def snapshot():
    # name + mtime + size: catches adds, deletes, renames and edits
    return [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in items()]


lines = []  # the full laid-out board, rebuilt only when files or the pane size change
offset = 0  # how many lines the board is scrolled down


def build():
    global lines
    # w - 1: a line filling the last column leaves the cursor in a "pending wrap" state
    # where the clear-to-end-of-line in show() would erase its final character.
    cells = [cell([clean(l) for l in render(p)]) for p in items()]
    lines = layout(cells, shutil.get_terminal_size().columns - 1)


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


def watch():
    global offset
    restore = raw_mode()
    sys.stdout.write(MOUSE_ON)  # ask for wheel events; tmux then forwards them instead of entering copy mode
    try:
        # ponytail: polls mtimes every 0.1s; use fswatch/kqueue if the board grows to many files
        last, size, resized_at = None, shutil.get_terminal_size(), 0.0  # resized_at 0 = none pending
        while True:
            ticks = scroll_ticks(wait_input(0.1))  # wait up to 0.1s for mouse input
            if ticks:
                offset += ticks * SCROLL_STEP
                show()
            # Resizes, incl. divider drags: Windows has no SIGWINCH, so on both systems compare the
            # size each pass (at most 0.1s apart).
            if shutil.get_terminal_size() != size:
                size, resized_at = shutil.get_terminal_size(), time.monotonic()
            try:
                now = snapshot()
                # A drag fires many resizes; redraw once they've stopped.
                settled = resized_at and time.monotonic() - resized_at > RESIZE_SETTLE
                if now != last or settled:
                    # Clear only a settled resize, and before building: one that arrives mid-build
                    # or mid-drag stays pending and gets its own redraw at the new size.
                    if settled:
                        resized_at = 0.0
                    build()
                    show()
                    last = now
            except FileNotFoundError:  # file deleted mid-scan; next poll catches up
                pass
    finally:  # always hand the terminal back: mouse reporting off, normal input mode
        sys.stdout.write(MOUSE_OFF)
        sys.stdout.flush()
        restore()


if __name__ == "__main__":
    if "--watch" not in sys.argv:
        build()
        show()
        sys.exit()
    for sig in ("SIGTERM", "SIGHUP"):  # pane killed/closed: exit via finally, not abruptly
        if hasattr(signal, sig):  # Windows has no SIGHUP
            signal.signal(getattr(signal, sig), lambda *_: sys.exit())
    try:
        watch()
    except KeyboardInterrupt:
        pass
