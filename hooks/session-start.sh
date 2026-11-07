#!/bin/sh
# Claude Code SessionStart hook: tell the agent about the whiteboard above it.
# Silent unless a whiteboard is open: WHITEBOARD_DIR comes from the environment, or, for agents
# inside herdr, from the running `whiteboard` tmux session (gone when the whiteboard is closed).
if [ -z "${WHITEBOARD_DIR:-}" ] && [ "${HERDR_ENV:-}" = 1 ]; then
  WHITEBOARD_DIR=$(tmux -L whiteboard show-environment -t whiteboard WHITEBOARD_DIR 2>/dev/null | cut -d= -f2-)
fi
[ -n "${WHITEBOARD_DIR:-}" ] && [ -d "$WHITEBOARD_DIR" ] || exit 0
cat >/dev/null  # drain hook input

cat <<EOF
You are running inside **whiteboard**: the user sees a whiteboard pane above this chat, rendered live from $WHITEBOARD_DIR. It holds long-lived info the user will refer back to (bug lists, plans, decisions, diagrams). Short-lived discussion stays in chat.

- One file per item: NN-name.md for text, NN-name.mmd for a Mermaid flowchart (graph TD/LR only). NN sets left-to-right order.
- Items render left to right in alphabetical order, wrapping into rows; anything past the pane edge is cut off. Keep each one compact and narrow (~40 columns of text).
- Update items in place as things change (e.g. tick off a bug with [x]). Delete the file when the user is done with it.
- When you put something on the board, say so in one line instead of repeating it in chat.

Currently on the board: $(ls "$WHITEBOARD_DIR" | tr '\n' ' ')
EOF
