# Cumulative update — 0.9.0-alpha

Base: complete Carisma Display Control 0.8-alpha AKP03E package.

1. Stop server/controllers and privately back up the installation, especially `data/`.
2. Extract the patch beside `server.py`, replacing application files. It excludes `data/`, keys and `Config_Locale.bat`; retain them.
3. Restart server/controllers and reload all Prompt pages. Do not mix 0.8 and 0.9 pages.
4. Test jog, speed, pause, cues, blackout and server-restart continuity on a rehearsal script.
5. Set the organization name/logo in Settings and optionally apply the suggested theme.

Rollback requires the complete backup, including data. A deduplication table is added automatically; it stores no administrator passwords. The full package excludes FFmpeg/NDI binaries and installed HID dependencies. See [README.md](README.md) and [TEST_REPORT.md](TEST_REPORT.md); alpha hardware validation remains required.
