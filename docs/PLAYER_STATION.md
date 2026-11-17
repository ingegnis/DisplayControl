# Local player station — Raspberry or PC

For installation today on Raspberry Pi OS Desktop, use the [complete Raspberry installer guide](RASPBERRY_INSTALL.md). It installs the local station, supervised Chromium, user service and desktop/labwc autostart while retaining private data. The generator described below remains a manual alternative; do not enable both launchers.

`player_station.py` serves the bundled player shell on localhost and proxies only scoped player APIs to the server/coordinator. It needs Python 3.9+ and a browser; no third-party Python packages. The interface can load even when the remote server is unavailable. Script/media continuity still requires a completed first synchronization and persistent browser storage.

Prompt example:

```sh
python player_station.py --server http://COORDINATOR-IP:8787 --mode prompt
```

Signage example, on a separate station:

```sh
python player_station.py --server http://COORDINATOR-IP:8787 --mode signage
```

Open `http://127.0.0.1:8877/` on that station and pair using a code generated in the console. Pair PRIMARY and BACKUP separately. The local service remembers only its own scoped identity in `data/station.json`; administrator, SHOW PACKAGE and cluster APIs are blocked. Neither it nor the player needs an administrator key. Pairing does not change the show on the server.

Subsequent runs need only `python player_station.py`; retain `data/station.json`, localhost port and browser profile. To move to another server, create a new station configuration and pair again. Use `--config` and a distinct `--port` for two independent stations on a development PC.

## Linux/Raspberry desktop startup

Prepare the OS desktop, Python 3 and Chromium. Run the generator **on the destination machine** so it records correct paths:

```sh
python3 prepare_kiosk.py --server http://COORDINATOR-IP:8787 --mode prompt
```

If browser discovery fails, pass `--browser /actual/path/to/chromium`. The generator creates a user systemd service, desktop autostart file, waiting launcher and installation instructions under `data/kiosk-setup/`. It does not install or enable them automatically. Follow `INSTALL.txt` as the kiosk user; configure desktop auto-login using the OS tools. No SD card is formatted or firmware modified.

The service restarts locally after process failure. The browser launcher waits for the local shell before opening kiosk mode. Keep the generated folder at its original path. Use separate SD/storage and power for PRIMARY/BACKUP, HDMI from each player to its monitor, and LAN from each player to the switch. TAKE remains logical; physical HDMI failover is external.

On Windows/macOS start the Python command and open the local URL; the Linux service generator is not a Windows service installer.

## Verify before use

Wait for the complete script or media cache. Test link loss, server/coordinator restart, browser reopening, station-service restart and real power interruption. Check fonts, screen orientation, HDMI, audio/codec support, memory/temperature and long-duration stability. Clearing browser data also clears cached show media; the local service can restore the scoped identity, not erased media.

Local HTTP/browser tests do not certify Raspberry SD durability, hardware acceleration or TV power state. Chromecast continues to use the Android TV build/install workflow; this station service is for Raspberry/PC browser hosts and does not claim native Python support on Chromecast.
