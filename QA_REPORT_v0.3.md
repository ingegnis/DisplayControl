> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.3.0

Six real loopback HTTP tests passed: authentication, heartbeat, invalid payloads, revisions, SQLite restart persistence and upload/hash/download.

Browser fixtures checked full-console player creation/selection, separate clock windows, assignment delivery, offline isolation/reconnect, hidden-control recovery and window reuse. Compact-demo checks covered a fifth named player, themes, fullscreen, two independent windows, offline schedules/clock, console closure/reopening, blocked-popup help and safe escaping. No external requests or JS errors; mobile 390 px had no horizontal overflow.

Managed Chromium blocked URL/file navigation. Actual HTML/CSS/JS ran in blank pages with real popups and test URL/memory-storage adapters. Rendering/timing/command isolation were checked; HTTP browser navigation, disk storage, popup permissions and physical offline restart were not certified. Backend HTTP tests used no adapters.

This version has browser players only: no Android APK, native Chromecast decoder or NDI gateway. Compact-demo media are built in; console previews are not remote screenshots. Browser fullscreen/background/file behavior needs target-PC testing. HTTP is for trusted LAN only.
