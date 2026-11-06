#!/usr/bin/env python3
"""Checks for board.layout. Run: python3 test_board.py"""
from board import GAP, cell, layout

box = lambda w, h: cell(["x" * w] * h)

# fits in one row: 10 + gap + 10
out = layout([box(10, 2), box(10, 2)], 10 + len(GAP) + 10, 24).splitlines()
assert len(out) == 2 and out[0] == "x" * 10 + GAP + "x" * 10, out

# third box doesn't fit: wraps below, separated by a rule
out = layout([box(10, 2), box(10, 2), box(10, 2)], 30, 24).splitlines()
assert len(out) == 5 and out[2] == "─" * 30 and out[3] == "x" * 10, out

# row height = tallest cell; shorter cell is padded with blanks
out = layout([box(5, 1), box(5, 3)], 40, 24).splitlines()
assert len(out) == 3 and out[2] == " " * 5 + GAP + "x" * 5, out

# wider than the pane: cropped on the right, nothing else breaks
out = layout([box(50, 2)], 20, 24).splitlines()
assert out == ["x" * 20] * 2, out

# taller than the pane: cropped at the bottom
assert len(layout([box(5, 40)], 80, 10).splitlines()) == 10

# empty board
assert layout([], 80, 24) == ""

print("ok")
