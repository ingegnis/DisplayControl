# Cumulative update — 0.10.0-alpha

Applies to the complete 0.8-alpha AKP03E package or 0.9, including 0.9 synchronization and organization branding. Back up the installation and `data/` privately before updating.

1. Stop the server and all controller instances.
2. Extract the patch beside `server.py`, replacing application files.
3. Run `Installa_Controller_Windows.bat` or `sh Installa_Controller_Linux_Mac.sh`. Neo requires Pillow as well as hidapi; both use `.controller-venv/`.
4. Existing AKP03E pairing is reused. Pair a new workstation once with a code from Prompt.
5. Restart the server and unified controller service; reload console and players.
6. Close vendor control apps, connect a supported controller and follow [CONTROLLERS.md](CONTROLLERS.md) for physical checks.

The patch excludes data, tokens, databases, virtual environments, local configuration and vendor binaries. Keep existing files; legacy AKP03E launchers and configuration remain compatible. The full package starts a new installation without transferring private scripts, credentials or media. Update outside show time; physical controller validation remains pending.
