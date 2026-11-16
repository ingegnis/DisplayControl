#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 diagnose_ndi.py "$@"
