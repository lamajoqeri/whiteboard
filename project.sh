# Sourced by the launcher and the hook, so both agree on the project and its tmux session.
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
# tmux names can't contain . or :, and the hash keeps two folders both called "api" apart.
S=wb-$(basename "$ROOT" | tr -c 'A-Za-z0-9_\n-' _)-$(printf %s "$ROOT" | cksum | cut -d' ' -f1)
