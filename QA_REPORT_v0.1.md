> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.1.0

JavaScript parsing/Python compilation and six real HTTP server tests passed: authentication, heartbeat, invalid payloads, revision conflicts, SQLite restart persistence, upload/MIME/hash/download. Chromium checks covered navigation, assignments, schedules crossing midnight and desktop/mobile layout (390 px, no overflow).

Player fixtures retained a program during simulated API loss and applied pending updates on reconnection. Real MP4 decoding advanced from 5 to 35 frames during API loss. An incomplete media update preserved the previous valid program; demo NDI used explicit fallback.

Browser navigation was blocked by environment policy. Actual HTML ran with memory localStorage/IndexedDB and a bridge to real HTTP APIs; adapters were test-only. Native browser storage, service workers and cold-start offline were not verified. No NEXCOM, Debian device, Chromecast G454V, bootloader, real NDI, power recovery, hardware acceleration, videowall or 24-hour test. NDI gateway and Android app were not implemented in 0.1.
