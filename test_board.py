#!/usr/bin/env python3
"""Checks for board layout and scrolling. Run: python3 test_board.py"""
from board import GAP, cell, clamp, layout, scroll_ticks

box = lambda w, h: cell(["x" * w] * h)

# fits in one row: 10 + gap + 10
out = layout([box(10, 2), box(10, 2)], 10 + len(GAP) + 10)
assert len(out) == 2 and out[0] == "x" * 10 + GAP + "x" * 10, out

# third box doesn't fit: wraps below, separated by a rule
out = layout([box(10, 2), box(10, 2), box(10, 2)], 30)
assert len(out) == 5 and out[2] == "─" * 30 and out[3] == "x" * 10, out

# row height = tallest cell; shorter cell is padded with blanks
out = layout([box(5, 1), box(5, 3)], 40)
assert len(out) == 3 and out[2] == " " * 5 + GAP + "x" * 5, out

# wider than the pane: cropped on the right, nothing else breaks
assert layout([box(50, 2)], 20) == ["x" * 20] * 2

# taller than the pane: layout keeps every line (show() windows it)
assert len(layout([box(5, 40)], 80)) == 40

# empty board
assert layout([], 80) == []

# scroll clamping: 40 lines in a 10-line pane can scroll 0..30
assert clamp(-5, 40, 10) == 0
assert clamp(12, 40, 10) == 12
assert clamp(99, 40, 10) == 30
assert clamp(3, 5, 10) == 0  # board shorter than the pane: never scrolls

# wheel parsing: SGR mouse codes, 64 = up, 65 = down, clicks ignored
assert scroll_ticks("\033[<65;10;5M\033[<65;10;5M") == 2
assert scroll_ticks("\033[<64;1;1M") == -1
assert scroll_ticks("\033[<0;3;4M\033[<0;3;4m") == 0

# file reading: binary gets a label, bad UTF-8 doesn't crash, hidden files are skipped
import tempfile
from pathlib import Path
import board

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR")
    (d / "notes.txt").write_bytes(b"caf\xe9 ok")  # latin-1, invalid UTF-8
    (d / ".01-bugs.md.swp").write_bytes(b"b0VIM\0junk")
    assert board.render(d / "chart.png") == ["chart.png: binary file (png)"]
    assert board.render(d / "notes.txt") == ["caf� ok"]
    (d / "flow.mmd").write_text("graph TD\nA --> B\n")
    real, board.HERE = board.HERE, d  # no bin/mermaid-ascii under d
    assert board.render(d / "flow.mmd") == ["flow.mmd: mermaid-ascii not installed"]
    board.HERE = real
    (d / "flow.mmd").unlink()
    board.BOARD = d
    assert [p.name for p in board.items()] == ["chart.png", "notes.txt"]

print("ok")
