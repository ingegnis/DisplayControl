#!/bin/sh
set -eu
if [ "$(id -u)" = 0 ]; then
    echo 'Run as the desktop user, without sudo. The installer requests sudo for OS packages and screen settings.' >&2
    exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required. Use Raspberry Pi OS with desktop.' >&2; exit 1; }
task_source=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$task_source/raspberry/install.py" "$@"
