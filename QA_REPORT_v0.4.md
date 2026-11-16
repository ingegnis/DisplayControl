> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.4 NDI gateway

**15 Python tests passed**, about eight seconds in the original environment. Real FFmpeg produced H.264/AAC fMP4, played by Chromium. No official NDI runtime or physical transmitter was available.

Coverage: protected APIs/segments, wrong keys, SQLite/revisions, uploads/hash/download, rejected payloads/profiles, 64-bit ABI sizes (video v2 72 bytes, audio v2 56), stride copies, planar/interleaved audio, missing-runtime errors, shared encoders/input limits, path traversal and stale-signal health. A locally compiled fake C ABI exercised discovery, frame-sync, buffer counts/padding/audio, raw FFmpeg input and decoding; it did not test the NDI protocol or official SDK.

```sh
python3 -m unittest discover -s tests -v
```

Browser fixtures checked 640×360 playback (readyState 4, advancing time, about 1.8 s queue), player assignment, mute toggle, simulated disconnect/reconnect, real encoder-stop fallback/recovery, two pages sharing one encoder and mobile 390 px. No listening test or end-to-end latency measurement.

Managed browser policy blocked HTTP/file navigation. `set_content` used memory storage and an explicit bridge to real APIs; FFmpeg/MP4 bytes were real. This does not validate direct LAN navigation, service workers, persistent storage or popup permissions. After runner timeout, two-player/mobile checks completed separately; no failed assertion was discarded.

Still required: official runtime with HB then specific HX/H.265 source, audible AV sync, NEXCOM capacity/temperature, physical LAN/mDNS/firewall recovery, native Windows/browser permissions, offline cold-start, 24/7 stability/log rotation/security review. No Chromecast, firmware or bootloader changes.
