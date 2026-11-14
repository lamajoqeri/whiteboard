# whiteboard
an effort to make coding with an agent (or many) resemble discussing with a colleague in front of a whiteboard

## Requirements
- [herdr](https://herdr.dev) 0.8.2 or newer (first release with Windows support out of beta)
- Python 3.9 or newer
- tmux on macOS/Linux, [psmux](https://github.com/psmux/psmux) on Windows
- Optional, for `.mmd` diagrams: [mermaid-ascii](https://github.com/AlexanderGrooff/mermaid-ascii/releases),
  saved as `bin/mermaid-ascii` (`bin/mermaid-ascii.exe` on Windows) in this repo

## Install

### macOS / Linux
```sh
git clone https://github.com/lamajoqeri/whiteboard.git ~/Projects/whiteboard
ln -s ~/Projects/whiteboard/whiteboard.py ~/.local/bin/whiteboard  # any folder on your PATH
```

### Windows (not yet tested)
```powershell
winget install psmux
git clone https://github.com/lamajoqeri/whiteboard.git $HOME\Projects\whiteboard
# put the repo folder on your PATH, so `whiteboard` runs whiteboard.cmd
$p = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$p;$HOME\Projects\whiteboard", "User")
```

### Agent hook (both)
Tells Claude Code agents about the board when their project's whiteboard is open.
Add to `~/.claude/settings.json` (Windows: `%USERPROFILE%\.claude\settings.json`), using your clone's path:
```json
"hooks": {
  "SessionStart": [
    { "matcher": "*", "hooks": [
      { "type": "command", "command": "python3 '/Users/you/Projects/whiteboard/whiteboard.py' hook", "timeout": 5 }
    ] }
  ]
}
```
On Windows the command is `py -3 "C:/Users/you/Projects/whiteboard/whiteboard.py" hook`.
If you already have SessionStart hooks, add this one to that list.

## Use
- `cd` into a project and run `whiteboard`: the board is on top, herdr below. Run it again to reattach.
- Board items live in the project's `.whiteboard/` folder, one file per item.
- See open whiteboards: `tmux -L whiteboard ls`. Close one: `tmux -L whiteboard kill-session -t <name>`
  (`psmux` instead of `tmux` on Windows).
- Tests: `python3 test_board.py` and `python3 test_whiteboard.py`.
