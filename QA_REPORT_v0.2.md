> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.2 clock/date

Node syntax and the original six server tests passed. Chromium/Playwright checked clock assignment, Europe/Rome, advancing time with network disabled, retained programs, reconnect updates, offline schedules, live fallback, midnight/date rollover, reduced motion and all three themes. Library create/edit/save, timezone rejection, hide-seconds, playlists and one-time project migration were checked. No JS errors/external clock requests; no horizontal overflow at 390 px. Inspected widths: 1280×720, 1440 and 390 px.

Browser policy blocked URL/file navigation; `set_content`, memory storage and a demo-mode test harness were used without changing delivered code. HTTP server tests ran separately. These checks do not verify native IndexedDB persistence, end-to-end installation or cold-start offline. No Chromecast/NEXCOM tests. Clock rendering uses HTML/CSS and system time, not NDI/video.
