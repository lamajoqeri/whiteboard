#!/bin/sh
# Checks for project.sh and the SessionStart hook. Run: sh test_hook.sh
# Uses a stub tmux, so it never touches a running whiteboard.
HERE=$(cd "$(dirname "$0")" && pwd -P)
T=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/a/api/src" "$T/a/api/.whiteboard" "$T/b/api" "$T/plain" "$T/my.app:x"
git -C "$T/a/api" init -q
git -C "$T/b/api" init -q
# stub: only the session named in $OPEN exists (args: -L whiteboard has-session -t =NAME)
printf '#!/bin/sh\n[ "$5" = "=$OPEN" ]\n' > "$T/bin/tmux"
chmod +x "$T/bin/tmux"

check() { [ "$2" = "$3" ] && return; echo "FAIL $1: got '$2', want '$3'"; exit 1; }
root() { (cd "$1" && . "$HERE/project.sh" && echo "$ROOT"); }
name() { (cd "$1" && . "$HERE/project.sh" && echo "$S"); }
hook() { (cd "$1" && OPEN=$2 PATH="$T/bin:$PATH" sh "$HERE/hooks/session-start.sh" </dev/null); }

A=$(name "$T/a/api")
check "subfolder uses the git root" "$(root "$T/a/api/src")" "$T/a/api"
check "subfolder shares the session" "$(name "$T/a/api/src")" "$A"
check "no git: this folder" "$(root "$T/plain")" "$T/plain"
[ "$A" != "$(name "$T/b/api")" ] || { echo "FAIL same-named folders collide"; exit 1; }
case $(name "$T/my.app:x") in *.*|*:*) echo "FAIL bad characters in session name"; exit 1;; esac

case $(hook "$T/a/api/src" "$A") in
  *"$T/a/api/.whiteboard"*) ;;
  *) echo "FAIL open whiteboard: agent not briefed"; exit 1;;
esac
check "no whiteboard open: silent" "$(hook "$T/a/api" none)" ""
check "other project's whiteboard: silent" "$(hook "$T/b/api" "$A")" ""
echo ok
