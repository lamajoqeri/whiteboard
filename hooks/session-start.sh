#!/bin/sh
# Claude Code SessionStart hook: tell the agent about its project's whiteboard, if one is open.
# A plain `herdr` and a whiteboard's bottom pane are the same herdr, so an agent can't tell how it
# was started. What decides it is whether a whiteboard session is open for this agent's project.
cat >/dev/null  # drain hook input
. "$(dirname "$0")/../project.sh"
tmux -L whiteboard has-session -t "=$S" 2>/dev/null || exit 0
WHITEBOARD_DIR=$ROOT/.whiteboard

cat <<EOF
You are running inside **whiteboard**: the user sees a whiteboard pane above this chat, rendered live from $WHITEBOARD_DIR. It holds long-lived info the user will refer back to (bug lists, plans, decisions, diagrams). Short-lived discussion stays in chat.

- One file per item: NN-name.md for text, NN-name.mmd for a Mermaid flowchart (graph TD/LR only). NN sets left-to-right order.
- Items render left to right in alphabetical order, wrapping into rows; anything past the pane edge is cut off. Keep each one compact and narrow (~40 columns of text).
- Update items in place as things change (e.g. tick off a bug with [x]). Delete the file when the user is done with it.
- When you put something on the board, say so in one line instead of repeating it in chat.

Currently on the board: $(ls "$WHITEBOARD_DIR" | tr '\n' ' ')
EOF
