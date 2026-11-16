# Changelog

## Unreleased

- Monitor opens with the panel matrix; More/Less toggles controls and details without pausing collection. Errors and stale indicators stay visible.
- Illustrated guides with 16 screenshots of current pages, using disposable browser demo data.
- Paired signage players start with their scoped token instead of requesting an administrator key; browser regression covers the real pairing flow.
- Refresh the offline shell cache for the updated pages.

## 0.10.0-alpha

- Background USB hub: automatic detection and hot swap for AJAZZ AKP03E, Contour ShuttleXpress/PRO v2, MSD-TWO and Stream Deck Neo.
- Separate HID, command and telemetry paths; STOP priority, command expiry, USB generation isolation and duplicate-instance lock.
- Isolated installers and legacy AKP03E launchers; PLAY restarts from zero speed after STOP.
- 151 Python tests passed; no physical controller testing. See TEST_REPORT.md.

## 0.9.0-alpha

- Fixed virtual Prompt layout, shared timeline and restart recovery.
- Organization name, compact logo and suggested logo colors.
- HID/HTTP/OSC resilience, per-Core tokens and per-database deduplication.
- Deterministic SQLite closure on Windows; FFmpeg/ABI regression; public-source sanitization.

## 0.8.0-alpha

- Direct AKP03E HID (`0300:3002`), six dynamic LCDs, three pressable encoders and three side keys.
- Scoped controller pairing/API, heartbeat and logical PRIMARY/BACKUP TAKE, including OSC.
- Optional HTTP-to-OSC fallback; Windows setup/diagnostics and Linux udev rule.

## 0.7-alpha

- TXT/DOCX teleprompter, cues, local scroll/cache and three typography/color presets.
- Keyboard jog/shuttle; UDP OSC listener (default 9000), optional IP allowlist.
- PRIMARY/BACKUP mirror status, position delta, `/prompt.html` and `/prompt_player.html`.

## 0.5.2-alpha

- On-demand player thumbnails, 1/2/5 s refresh, status/fallback and scoped access.
- Includes 0.5.1 latency changes. See LEGGIMI_MONITOR_v0.5.2.md.

## 0.5.1-alpha

- 0.5 s target segments, aligned keyframes, 0.75 s target queue, 100 ms polling and catch-up.
- Stable comparison mode (`--live-mode` / `CARISMA_LIVE_MODE`); queue distinguished from total latency.
- 75 Python tests, 17 JS checks and browser fixtures; data/pairing/runtime/firewall unchanged.

## 0.5-alpha

- Explicit LAN startup, one-use eight-digit pairing and per-screen credentials.
- Scoped state/media/heartbeat/gateway, token revocation/replacement and attempt limits.
- Dedicated offline shell; Android TV Java/WebView sources, remote menu, SDK builder and ADB helper.
- No compiled APK or physical Android/Chromecast validation.

## 0.4.1

- Selective Windows dependency repair; verified FFmpeg download, safe extraction, staging and backup.
- Hashed/signed Python x64 bootstrap; visible NDI installer/license/UAC.
- Real H.264/AAC smoke test, diagnostic-only mode and saved paths/logs. Zero NDI sources is a warning.
- Data, schedules, local configuration and firewall unchanged.

## 0.4

- Server-side NDI ctypes receive/frame-sync, shared FFmpeg H.264/AAC fMP4 and local MediaSource client.
- Discovery/manual sources, profiles, preview, idle shutdown, signal recovery, fallback and optional audio.
- Explicit non-NDI generator; no bundled runtime/FFmpeg. 15 Python tests passed; real NDI pending.
- Compact demo shares the full console.

## 0.3.0

- Add/edit/delete players, groups and clock themes; named fullscreen windows with hideable controls.
- Local window messaging, last-program memory, offline simulation and storage/message fallbacks.
- Clearer full-console player creation/selection and popup handling, 16:9 player window.
- No new dependencies, Chromecast or NDI integration.

## 0.2.0

- Local clock/date content with three themes, animated digits, timezone/seconds and Italian date.
- Library, screen, schedule, playlist and fallback support; reduced-motion preference.
- Non-destructive 0.1 migration and shell cache update. Earlier browser/NDI limits remain.
