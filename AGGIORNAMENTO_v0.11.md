# Cumulative update — 0.11.0-alpha

Applies over complete 0.8-alpha AKP03E, 0.9 or 0.10. Back up the whole installation and private data first.

1. Stop server, controller, coordinator and local station processes. Extract the patch beside `server.py`, replacing application files and merging subfolders.
2. Retain `data/`, local configuration, `.setup/`, `.controller-venv/`, vendor dependencies and signing keys. None is included in the patch.
3. Start standalone `server.py` for the existing mode, or follow [CLUSTER.md](docs/CLUSTER.md) to configure three machines. Do not create competing coordinators. The reserve receives Core A's authoritative private copy.
4. Move browsers/controllers to the coordinator origin and pair for that origin when enabling HA. Wait for replica alignment.
5. Open SHOW PACKAGE, export a private backup, verify a rehearsal package and activate in STOP. Check every destination and script before PLAY.
6. Reload console/player pages. The shell cache version changes; existing media/cache and pairing data need not be erased.
7. Prepare local Raspberry/PC stations using [PLAYER_STATION.md](docs/PLAYER_STATION.md). Follow [DEVICE_SETUP.md](docs/DEVICE_SETUP.md) for physical acceptance.

The full software ZIP supports new installations but does not transfer private show data. SHOW PACKAGE transfers content; private HA replication transfers operational identity/state. Rollback to an older application needs the full pre-update private backup. Do not mix application versions across Cores or update during a performance.

Hardware validation remains required. Android build/signing prerequisites and SDK license acceptance are separate from source installation; no tested Chromecast hardware is supplied by this update.
