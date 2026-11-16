# DisplayControl 0.10.0-alpha test report

Release checks: 2026-11-16, Windows x64, Python 3.14.7, Node.js, hidapi 0.15.0, Pillow 13.0.0, FFmpeg/ffprobe and Visual C.

**151 Python tests passed: no errors, failures or skips**, including 24 hub tests. Three JavaScript suites passed; 20 scripts passed syntax checks. Clean isolated dependency installation and legacy `akp03e_controller.py --list` succeeded. Real HID enumeration found **zero supported physical controllers**.

| Area | Coverage | Method |
|---|---|---|
| Detection | VID/PID, interfaces, unknown-device/keyboard exclusion | Synthetic metadata |
| AJAZZ | Encoders, buttons, ACK signature, both identities | Synthetic reports |
| MSD-TWO | Protocol 2 clicks, LCD and padding | Simulated HID |
| Contour | Signed ring, center STOP, jog wrap, simultaneous buttons, PRO map | Synthetic reports |
| Neo | Eight keys, two touch buttons, edges, JPEG 96×96, packets, brightness | Real Pillow; simulated HID |
| Swap | AJAZZ → MSD-TWO → Contour → Neo, one pairing, no Prompt page | Real loopback HTTP; simulated USB |
| Unplug | Stale queues rejected after reconnection | Simulated USB |
| Duplicate start | Configuration lock and process-exit release | Real Windows file lock |
| Responsiveness | STOP priority, expiry, blocked polling leaves commands running | Controlled concurrent tests |
| Status privacy | No tokens, USB paths or serials in heartbeats | API and fixtures |
| PLAY | Resume from STOP at zero speed | Real HTTP |
| Regression | Server, pairing, tokens, revocation, Prompt, Monitor, players | Full suite |
| FFmpeg | 360p/720p, fragments, keyframes, access, audio/video decoding | Real FFmpeg |
| NDI | C binding, signal loss/recovery, encoding | Fake ABI DLL; no real NDI source |
| Android | Policy, manifest, asset consistency | Sources only; APK not built/run |

The controller API test runs without browser pages or keyboard shortcuts. It verifies the background command path, not physical drivers or OS permissions.

## Historical evidence

`test-results/browser-sync.json` records **0.9** browser checks at 800×600 and 1920×1080, including server restart. These are historical Prompt measurements, not new 0.10 browser or hardware tests. The preceding report is in tag `v0.9.0-alpha`; 0.10 JavaScript checks cover syntax and automated regression.

## Unverified

No physical AJAZZ, Contour, Mars Gaming or Elgato was available. Firmware, real USB identities, button numbering, LCD orientation, vendor conflicts, unplug recovery and stage latency require device tests. macOS/Linux HID access and udev permissions were not tested here. Unknown USB revisions are ignored; use [controller diagnostics](CONTROLLERS.md).

Server and service must run to receive new commands. USB reads are separate from networking, but in-flight HTTP can delay commands. STOP is not a hardware emergency stop. Unplugging does not stop scrolling; centering Contour does. Deduplication is per Core; OSC has no acknowledgement.

No real network NDI, Raspberry, Chromecast, QLab, HA cluster or HDMI switching tests. TAKE is logical. The release remains alpha.

## Reproduce

Commands: [README.md](README.md). Sanitized logs and summaries: [test-results/](test-results/README.md). Full coverage needs controller dependencies, FFmpeg/ffprobe and a C compiler. Keep data, tokens and virtual environments private.

## Editorial revision — 2026-11-16

After compacting English comments and documentation, all 151 Python tests passed again (43.948 s, no skips), as did three JavaScript suites and 20 syntax checks. Python AST/token comparison and non-comment source comparison found no executable changes. Shared Android/browser assets matched; 56 local documentation links resolved and original external reference URLs were retained. Original release evidence files and attachment checksums remain unchanged.

## Interface update — 2026-11-16

The unreleased matrix/More update passed all 151 Python tests again (47.004 s, no failures/errors/skips), three JavaScript suites and 20 script syntax checks. The shared browser/Android player assets remain identical.

Eight browser scenarios passed in local Chrome using real HTTP navigation and native browser storage: four players paired through `/connect.html` without an administrator key; default/collapsed views; keyboard More; columns, interval and group controls; pause/resume; continued polling and reload defaults; 390px layout; visible server-failure/recovery states. No page errors. Results: [browser-interface.json](test-results/browser-interface.json).

The run captured 16 screenshots with disposable demo data and no displayed credentials. Local documentation links resolved and screenshots were visually inspected. [Illustrated guide](docs/SCREENSHOTS.md).

This also fixes a pre-existing browser startup guard that requested administrator credentials after player pairing. The fix uses the existing scoped player transport; API authorization is unchanged. Offline shell cache was refreshed. No physical panels, USB controllers, official NDI source, Chromecast or Android APK was tested by this browser run. Original tagged release attachments and checksums are unchanged.
