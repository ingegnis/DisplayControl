> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.7 Prompt

Validated parser/cues (`[[CUE: ...]]`), stdlib TXT/DOCX import, normalized presets, play/pause/speed/jog/cue/blackout/messages, one-use PRIMARY/BACKUP pairing/readiness, admin/scoped-player access and OSC message/bundle codecs. A real loopback UDP `/carisma/prompt/speed` float was applied and recorded; this verifies the listener, not QLab or a stage LAN.

Targeted server/player/Prompt run: **32 tests passed**, including real FFmpeg scoped segments. Separate monitor run: **18 passed**, with `PYTHONPATH=tests:.` for standalone imports. Total: 50 targeted tests; do not add counts from other releases.

Static review covered disabled/loopback/LAN OSC, optional IP allowlist, local requestAnimationFrame scroll, 50 ms polling and historical keyboard reverse shortcuts Shift+Digit1–5.

No real QLab→LAN→stage path, Contour driver/profile, jog latency, Raspberry Pi 3 B/B+ boot/cache, SD/power-loss recovery, HDMI switch/second-monitor failover or sustained stress/24-hour operation was tested. Browser HTTP end-to-end and physical hardware were unavailable in that environment. Rehearse PRIMARY/BACKUP with separate LAN/power, manual input/failover and emergency script before show use.
