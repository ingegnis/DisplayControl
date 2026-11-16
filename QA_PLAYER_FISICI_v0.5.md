> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.5 player workflow

**65 Python tests passed**, 23.531 s: 39 existing, 17 player API, seven Android build-utility and two LAN-start checks. Desktop JDK 21 compiled Java 8-compatible `NetworkPolicy`: 27 checks passed. Eleven browser fixture scenarios and Python/XML/seven-script syntax checks completed. **No Android APK was built or installed**: SDK unavailable, build correctly failed without an APK; no Chromecast was reached.

Environment: Linux x86_64, Python 3.13.5, OpenJDK 21.0.12.1, FFmpeg 7.1.5, Chromium 144.0.7559.96. Not native Windows, NEXCOM or G454V.

Real loopback HTTP/SQLite tests covered admin-only pairing/revocation, expiry/attempt limits, single concurrent redemption, hashed/scoped tokens, assigned-media access/hash, heartbeat bounds, replacement/deletion, denied admin/other-player/encoder access, scoped real FFmpeg segments and explicit LAN binding. Java policy tested private IPv4, URL/port/path validation without DNS. Build utilities rejected unsafe ZIPs/hash mismatches and reused verified cache; TV manifest/assets were checked.

Unexecuted: sdkmanager, full Activity compilation against android.jar, D8/aapt2, signing, Windows PowerShell bootstrap and ADB. Desktop policy tests do not imply native Android success.

Browser scenarios: pairing UI, 390 px layout, scoped clock shell, link-loss retention, reconnect updates, injected-snapshot offline reopen, real MediaSource playback, two players sharing FFmpeg, live fallback/recovery and no unhandled JS errors. Managed policy blocked direct HTTP navigation; `set_content`, a real-API bridge and memory storage were explicit fixtures. Offline reopening did not verify IndexedDB persistence, actual LAN, Android WebView or hardware rendering.

On-site work remains: APK build/install, LAN/firewall, remote/audio/codecs, cache persistence, power/LAN recovery, clock drift, real NDI/HX, temperature/load and long runs. No autostart, launcher replacement, system watchdog, direct Chromecast NDI, frame-synchronized videowall or production TLS/multiuser support.

```sh
python -m unittest discover -s tests -v
javac --release 8 -d java-test android-player/src/it/carisma/player/NetworkPolicy.java android-player/PolicyTest.java
java -cp java-test PolicyTest
python build_android.py --sdk /actual-path/sdk
```

Browser runner: `python tests/browser_fixture_check.py` (development-only Playwright/Chromium; optional `CARISMA_QA_CHROMIUM`). SDK licenses must be accepted; build/signature/device success must be observed separately. Historical raw logs were omitted from the public repository.
