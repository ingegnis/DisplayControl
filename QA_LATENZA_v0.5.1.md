> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.5.1 buffering

Original 0.5 settings: one-second HLS/GOP, `end - 2`, 500 ms polling, catch-up above five seconds. These explain pipeline buffering, not all reported source-to-screen delay.

**75 Python tests passed** (65 existing + ten policy/segment tests); 17 JavaScript policy/bounds/recovery/copy checks and syntax checks passed. Eleven browser scenarios covered pairing, UI/content/clock, fallback/reconnect and shared encoding. Real FFmpeg checked responsive 360p/720p and stable 360p durations, keyframes, AV decoding and HLS metadata. A five-second manifest stall and live button tested recovery. Final runs followed correction of an initial test syntax error.

Local FFmpeg `testsrc2` + AAC, 640×360/15 fps, Chromium/Linux; 50 queue samples every 200 ms:

| Measurement | Stable | Responsive |
|---|---:|---:|
| Mean queue | 1.807 s | 0.632 s |
| Minimum / maximum queue | 0.989 / 2.378 s | 0.334 / 0.914 s |
| First observed playback | 2.107 s | 0.871 s |
| Decoded / dropped frames | 150 / 0 | 150 / 0 |

Queue is `buffered.end - currentTime`; startup time is not image latency. No stall occurred in these samples; no 24/7 guarantee follows. Historical raw `qa_v051/latency-*.json` files are not included in the public repository.

Browser policy blocked direct HTTP (`ERR_BLOCKED_BY_ADMINISTRATOR`). `set_content`, a real local API bridge and memory storage were fixtures; FFmpeg/MP4/MediaSource decoding were real. No official NDI runtime, user source, UniFi LAN, native Windows, NEXCOM, Chromecast, audible AV sync, offline cold-start or long-run test. No NDI end-to-end latency was measured; prior user-reported operation was not observed here.

Changes: gateway responsive/stable policy and shorter segments, server `--live-mode`, bounded player catch-up/live button/queue label and shell cache version. No new runtime dependency or user-data migration. Technical references describe formats/queues; the measured values above are local test results, not vendor guarantees.

## References

- https://ffmpeg.org/ffmpeg-formats.html#hls-2
- https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-recv
