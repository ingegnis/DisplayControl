# DisplayControl 0.11.0-alpha test report

2026-11-16, Windows x64, Python 3.14.7, Node.js, portable OpenJDK 21.0.13, FFmpeg/ffprobe, Visual C, hidapi 0.15.0 and Pillow 13.0.0.

**177 Python tests passed in 71.018 s: no failures, errors or skips.** Three JavaScript suites passed; 22 scripts passed syntax checks. Thirty desktop Java NetworkPolicy checks passed; these are not Android Activity/SDK/device tests.

## Added in 0.11

| Area | Verified behavior | Evidence boundary |
|---|---|---|
| SHOW PACKAGE | Complete metadata/media round trip, SHA-256, missing/corrupt media, path rejection, revision conflicts, STOP activation, local identity preservation, rollback and expired preview cleanup | 13 automated tests; real ZIP/files/SQLite |
| Cluster authority | Bootstrap selection, no preemption, stale-replica exclusion, restart delay, process incarnation, namespace/sender-gated OSC relay | Unit tests and real UDP sockets |
| Commit fencing | Expired lease rolls SQLite transaction back before commit | Real SQLite transaction |
| Core failover | Three real processes; replicated state/identity; active-Core termination, reserve promotion, deduplicated controller request, continued writes, old-Core recovery, witness loss/restart | Real loopback HTTP and private checkpoints; no physical LAN/power claim |
| Local station | Scoped proxy, blocked administrator APIs, persisted token, shell availability through server outage | Real HTTP processes |
| Browser station | Prompt and signage pair at localhost; native cache survives reload and station-service restart with remote server stopped; Prompt scrolling continues | Actual Chrome/HTTP/localStorage/IndexedDB, no transport/storage adapters |
| Interface | Default monitor matrix, More/Less and keyboard, mobile 390px, pause/filter/refresh/columns, continued polling, failure/recovery; SHOW PACKAGE download/preview/activation/rollback; revoked player returns to pairing | Actual Chrome and loopback HTTP |

Full regression retains server/API/pairing, organization branding, Prompt timeline, Monitor, controller protocols/queues, real FFmpeg 360p/720p fragments/keyframes/AV decoding and a compiled fake NDI ABI with signal loss/recovery. The fake ABI is not the official runtime or an NDI transmitter.

## Evidence and repeatability

- [Python log](test-results/python-tests.txt), [summary](test-results/summary.json), [JavaScript](test-results/javascript.json).
- [Interface checks](test-results/browser-interface.json), [local station checks](test-results/browser-station.json).
- [17 illustrated main-page screenshots](docs/SCREENSHOTS.md), captured with disposable demo data; no active pairing codes or administrator keys displayed.
- Historical 0.9 browser-sync evidence remains labeled in `test-results/browser-sync.json`; previous release reports are retained in their Git tags.

```sh
python -m unittest discover -s tests -v
node tests/test_live_policy.js
node tests/test_branding.js
node tests/test_prompt_timeline.js
# Development-only Playwright and installed Chrome:
python tests/browser_docs_check.py
python tests/browser_station_check.py
```

FFmpeg/ffprobe and a C compiler are needed for non-skipped encoding/ABI tests. Server, coordinator and station use Python's standard library; HID/image dependencies are isolated for the controller service. Tests create disposable private data, never the installation's show directory.

## Practical limits

The coordinator is a required single lease authority and private recovery store. Its loss suspends new writes after lease expiry; open synchronized players retain local playback. Only configured Core failover is automatic. Live NDI pipelines may restart and use fallback. Unacknowledged/ambiguous mutations must not be blindly repeated; OSC has no delivery acknowledgement. HA files contain credentials and must remain private; SHOW PACKAGE excludes them.

Kiosk/service generators produce files; actual Linux/Raspberry desktop startup, SD cache durability, firmware, USB permissions, HDMI, audio, clocks, temperatures, physical network/power interruption and sustained load require on-site tests. No controller, Raspberry, Chromecast, QLab or real NDI source was available. TAKE remains logical, with external/manual HDMI switching.

Android sources are version 0.11 (versionCode 110). After SDK license acceptance, the native APK compiled and passed signature/alignment checks on 2026-11-17; see the [later build supplement](docs/ANDROID_BUILD_v0.11.md). The results above describe the original release regression. No APK/device certification is inferred from source or desktop Java checks. This is an alpha release prepared for physical acceptance, not a claim of complete production/hardware certification.
