#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3 non trovato. Apri index.html per la demo senza server.' >&2
  exit 1
fi
exec python3 server.py --open
