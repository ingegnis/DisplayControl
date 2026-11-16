> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.5.2 monitor

**93 Python tests passed** (75 regression + 18 monitor), 17 JavaScript policy/copy checks and 30 desktop Java NetworkPolicy checks. Java checks are not Android Activity tests. HTML script syntax and 14 browser monitor checks completed with four fixture players, real HTTP/FFmpeg/video/Canvas JPEGs.

Browser checks: real video frame versus labeled reconstructed clock; no collection before demand; authenticated preview display; no extra encoder/receiver; 1/2/5 s leases; group filter; new-content update; fallback marking; mobile 390 px; visibly stale/unreachable previews; reconnect refresh; pause/release without stopping players; resume; no JS errors. JPEG sizes: foyer-ingresso 8413, ingresso-sala 7308, camerini 7379, bar-foyer 7366 bytes. Graphics were reconstructions; video was local testsrc2, not NDI.

API tests covered administrator-only reads, own-player uploads, revocation/re-pairing/deletion, hidden tokens, JPEG dimensions/size, invalid input/rate limits, latest-image-only storage, lease expiry and multiple monitor intervals.

Includes 0.5.1 responsive buffering. Historical mean queue 1.807 → 0.632 s was a prior local comparison, not new monitor-open or source-to-screen measurement. Python regression rechecked fragments/keyframes/decoding; monitoring added no encoder.

Chromium/Linux used `set_content`, explicit real-API bridge and memory IndexedDB/localStorage because direct navigation was blocked. Not a native browser persistence, Windows/LAN/NEXCOM/Android/offline-boot test. No physical NDI, audible AV delay, TV/HDMI, APK, temperature or 24/7 checks. User-reported previous playback was not observed here.

A runner-interrupted first run was not counted. A complete rerun passed 93 tests in 40.412 s; its second-40 faulthandler dump was teardown diagnostics, not failure. Historical raw logs are excluded publicly.

```sh
python -m unittest discover -s tests -v
node tests/test_live_policy.js
# Development-only Playwright/Chromium:
python tests/browser_monitor_check.py
```

No Internet needed for monitor tests; real video tests need FFmpeg. Browser test dependencies are not production server dependencies.
