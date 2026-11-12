#!/usr/bin/env python3
"""Checks for the launcher's project/session naming and the hook. Run: python3 test_whiteboard.py
Fakes is_open(), so it never touches a running whiteboard."""
import subprocess, tempfile
from pathlib import Path
import whiteboard as wb

with tempfile.TemporaryDirectory() as t:
    t = Path(t).resolve()
    for d in ("a/api/src", "a/api/.whiteboard", "b/api", "plain", "my.app:x"):
        (t / d).mkdir(parents=True)
    for repo in ("a/api", "b/api"):
        subprocess.run(["git", "init", "-q", t / repo], check=True)
    (t / "a/api/.whiteboard/01-bugs.md").write_text("x")
    a = wb.session(t / "a/api")

    assert wb.project_root(t / "a/api/src") == t / "a/api", "subfolder uses the git root"
    assert wb.session(wb.project_root(t / "a/api/src")) == a, "subfolder shares the session"
    assert wb.project_root(t / "plain") == t / "plain", "no git: the folder itself"
    assert wb.session(t / "b/api") != a, "same-named folders get different sessions"
    assert not set(".:") & set(wb.session(t / "my.app:x")), "no . or : in session names"

    wb.is_open = lambda name: name == a  # only project a's whiteboard is open
    text = wb.briefing(t / "a/api/src")
    assert str(t / "a/api/.whiteboard") in text and "Currently on the board: 01-bugs.md" in text, text
    assert wb.briefing(t / "b/api") == "", "other project's whiteboard: silent"
    wb.is_open = lambda name: False
    assert wb.briefing(t / "a/api") == "", "no whiteboard open: silent"

print("ok")
