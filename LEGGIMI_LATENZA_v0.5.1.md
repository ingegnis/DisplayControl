# Live buffering — historical 0.5.1 guide

The 0.5 pipeline used one-second segments, `end - 2` startup, 500 ms polling and catch-up above five seconds. These add gateway/player delay; they do not identify the cause of all reported NDI latency.

## Update from 0.5

Stop the server and back up the installation. Extract `Carisma_Aggiornamento_Latenza_v0.5.1.zip` beside `server.py`, merging application files; do not run inside the ZIP. Restart `Avvia_Server_LAN_Windows.bat` and reload console and all players (Ctrl+F5). Keep browser data, cache and pairing. Check **Reattiva / LAN**, target buffer **0.75 s**, then use **Torna alla diretta**.

This patch requires 0.5, not standalone 0.4. It excludes `data/`, `bin/`, `.setup/`, `Config_Locale.bat`, keys and NDI libraries; no dependency or firewall changes.

| Setting | Stable / 0.5 | Responsive default |
|---|---:|---:|
| Segment target | 1 s | 0.5 s |
| Actual nominal segment, 15 fps | 1 s | 0.533 s / 8 frames |
| Actual nominal segment, 25 fps | 1 s | 0.520 s / 13 frames |
| Player queue target | 2 s | 0.75 s |
| Poll interval | 500 ms | 100 ms |
| Catch-up threshold | 5 s | 1.8 s |

Keyframes align with segments; obsolete segments are skipped after interruptions. Queue means `buffered.end - currentTime`, not end-to-end latency. The catch-up threshold is not a latency guarantee. Profiles remain 360p/15 fps and 720p/25 fps.

For more buffering, add to existing `Config_Locale.bat`, then restart/reload:

```bat
set "CARISMA_LIVE_MODE=stable"
```

Use `responsive` to restore the default, or:

```sh
python3 server.py --host 0.0.0.0 --port 8787 --live-mode responsive
# Alternative: --live-mode stable
```

Measure source-to-screen delay by filming the transmitted stopwatch beside the player and comparing values in the same frame. Repeat after startup and steady running; compare the local **NON NDI** generator with the real source and record CPU load. Change one load parameter at a time.

This remains fMP4 delivery, with no frame-accurate, 100 ms or lip-sync guarantee. Android sources are updated, but no new APK or Chromecast test is supplied; installed apps need rebuilding/reinstallation. Results: [QA_LATENZA_v0.5.1.md](QA_LATENZA_v0.5.1.md).
