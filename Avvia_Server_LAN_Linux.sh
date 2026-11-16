#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
printf '%s\n' 'Carisma / LAN fidata, TCP 8787. Nessuna modifica al firewall.'
exec python3 server.py --host 0.0.0.0 --port 8787 --prompt-osc-bind 0.0.0.0
