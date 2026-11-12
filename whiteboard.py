#!/usr/bin/env python3
"""whiteboard: board on top, herdr below, in a private tmux server, one session per project.

  whiteboard        open (or reattach to) this project's whiteboard
  whiteboard hook   Claude Code SessionStart hook: brief the agent if its project's board is open

On Windows the multiplexer is psmux, a native tmux port that takes the same commands."""
import json, os, re, subprocess, sys, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent  # resolve(): the command is a symlink to this file
# Call psmux by its own name: its tmux.exe alias can be shadowed, e.g. by Git Bash's MSYS tmux,
# which can't host Windows programs like herdr.exe.
MUX = "psmux" if os.name == "nt" else "tmux"


def tmux(*args, **kw):
    return subprocess.run([MUX, "-L", "whiteboard", *map(str, args)], **kw)


def project_root(cwd):
    """The git root, else the folder itself, so launcher and hook agree from any subfolder."""
    try:
        git = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if git.returncode == 0:
            return Path(git.stdout.strip()).resolve()
    except OSError:  # no git installed
        pass
    return Path(cwd).resolve()


def session(root):
    # tmux names can't contain . or :, and the hash keeps two folders both called "api" apart.
    return f"wb-{re.sub(r'[^A-Za-z0-9_-]', '_', root.name)}-{zlib.crc32(str(root).encode())}"


def is_open(name):
    try:  # "=": exact name match; tmux otherwise accepts any session whose name starts with this one
        return tmux("has-session", "-t", f"={name}", capture_output=True).returncode == 0
    except OSError:  # no tmux/psmux installed
        return False


def launch():
    root = project_root(os.getcwd())
    s, board = session(root), root / ".whiteboard"
    pane = f"={s}:"  # pane/option commands need the session written as a window target
    if not is_open(s):
        board.mkdir(exist_ok=True)
        # "--": the rest is the pane's command, run as argv (no shell re-parsing quotes in paths)
        tmux("new-session", "-d", "-s", s, "-c", root, "--", sys.executable, HERE / "board.py", "--watch", board)
        tmux("set", "-t", pane, "status", "off")
        tmux("set", "-t", pane, "mouse", "on")  # drag the divider to resize
        if MUX == "tmux":  # psmux doesn't forward passthrough yet
            tmux("set", "-t", pane, "allow-passthrough", "on")
    # Add herdr below the board: on a new session, and again if its pane closed (its server stopped,
    # e.g. for a herdr update), otherwise reattaching shows the board alone. Default herdr session.
    running = tmux("list-panes", "-t", pane, "-F", "#{pane_current_command}", capture_output=True, text=True)
    if "herdr" not in [c.removesuffix(".exe") for c in running.stdout.splitlines()]:  # psmux: herdr.exe
        tmux("split-window", "-v", "-l", "65%", "-t", pane, "-c", root, "--", "herdr")
    attach = [MUX, "-L", "whiteboard", "attach", "-t", f"={s}"]
    if os.name == "nt":  # no exec on Windows: run tmux and pass on its exit code
        sys.exit(subprocess.run(attach).returncode)
    os.execvp(MUX, attach)  # become tmux, so the terminal talks to it directly


def briefing(cwd):
    """What the hook tells an agent working in cwd: nothing unless its project's whiteboard is open.
    A plain `herdr` and a whiteboard's bottom pane are the same herdr, so how the agent was started
    can't tell them apart; whether a whiteboard session is open for its project does."""
    root = project_root(cwd)
    if not is_open(session(root)):
        return ""
    board = root / ".whiteboard"
    items = " ".join(sorted(p for p in os.listdir(board) if not p.startswith("."))) if board.is_dir() else ""
    return f"""You are running inside **whiteboard**: the user sees a whiteboard pane above this chat, rendered live from {board}. It holds long-lived info the user will refer back to (bug lists, plans, decisions, diagrams). Short-lived discussion stays in chat.

- One file per item: NN-name.md for text, NN-name.mmd for a Mermaid flowchart (graph TD/LR only). NN sets left-to-right order.
- Items render left to right in alphabetical order, wrapping into rows; anything past the pane edge is cut off. Keep each one compact and narrow (~40 columns of text).
- Update items in place as things change (e.g. tick off a bug with [x]). Delete the file when the user is done with it.
- When you put something on the board, say so in one line instead of repeating it in chat.

Currently on the board: {items}
"""


def hook():
    try:  # Claude Code sends the session as JSON on stdin, including the agent's working folder
        cwd = json.load(sys.stdin).get("cwd") or os.getcwd()
    except ValueError:
        cwd = os.getcwd()
    print(briefing(cwd), end="")


if __name__ == "__main__":
    hook() if sys.argv[1:] == ["hook"] else launch()
