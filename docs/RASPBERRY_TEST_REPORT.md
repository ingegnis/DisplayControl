# Raspberry installer 0.11-r2 â€” validation

2026-11-17. Target preparation: Raspberry Pi 3B+, Raspberry Pi OS Desktop, Python 3.11+, Chromium. Application runtime: 0.11.0-alpha.

- Thirteen installer/supervisor tests passed: URL rejection before writes, dry run, preserved pairing/cache on update, mode/server/port isolation, unmanaged startup refusal, malformed autostart refusal, profile/argument quoting, mocked browser crash restart/owned-process shutdown, runtime checksum rejection, official screen-tool invocation/verification, configuration backup, failed verification and missing-tool refusal.
- Three existing local station tests passed, including real HTTP pairing, persisted scoped identity and shell availability after Core loss.
- Standalone tar.gz extracted into a disposable directory: all runtime files/hashes matched; the extracted station paired against an actual disposable Core, retained identity across process restart and served the local Prompt shell after Core termination.
- Python syntax checks and shell syntax checks passed; generated launcher/manage scripts also checked. Bundled files are a strict runtime/documentation allowlist; no private configuration, keys, database, media, browser profile or vendor binaries are distributed.
- Core and Android source versions unchanged. This is a separately tagged installer add-on, not an Android/Core upgrade.

Environment: Windows host; systemd/apt/desktop integration and supervisor process operations are mocked in unit tests. Shell parsing uses Git Bash; real player HTTP processes use the host Python runtime. No Linux/ARM execution, Raspberry hardware, HDMI/audio, Pi boot, GPU acceleration, real power-loss durability or sustained thermal/load certification was available. These require the guide's on-device acceptance checklist. No performance guarantee is made for video/NDI on the 1 GB Pi 3B+.
