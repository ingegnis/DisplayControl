#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x .controller-venv/bin/python ]; then
    exec .controller-venv/bin/python controller_service.py "$@"
fi
exec python3 controller_service.py "$@"
