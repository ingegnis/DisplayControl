# NDI gateway — setup and historical 0.4 notes

Pipeline: NDI source → official runtime/frame-sync → server FFmpeg H.264/AAC fMP4 → browser MediaSource. Browsers do not decode NDI directly. Matching source/profile shares one encoder; different profiles require separate encoders. Default limit: two streams; `--ndi-max-streams` accepts 1–8, not a certified hardware capacity.

The pipeline was tested with a local generator and fake ABI. No official runtime/physical transmitter or NEXCOM validation is claimed. Segmentation adds latency; this is not a frame-synchronized videowall or guaranteed stage lip-sync monitor.

## Install

Python 3.9+ 64-bit, FFmpeg with libx264/AAC, and the official 64-bit NDI runtime for real reception. Server/gateway need no pip packages. FFmpeg does not need libndi support. Vendor binaries are not bundled; retain their licenses and runtime dependencies.

Windows: run `Verifica_NDI_Windows.bat` for selective repair or `Solo_Verifica_NDI_Windows.bat` for diagnosis only, then `Avvia_Windows.bat`. See [Windows setup](LEGGIMI_SETUP_WINDOWS_v0.4.1.md). Manual paths in `Config_Locale.bat`, copied from the example:

```bat
@echo off
set "CARISMA_NDI_LIBRARY=C:\actual-path\Processing.NDI.Lib.x64.dll"
set "CARISMA_FFMPEG=C:\actual-path\ffmpeg.exe"
```

Debian prerequisites and launch (replace the runtime path for your architecture):

```sh
sudo apt update
sudo apt install python3 ffmpeg avahi-daemon libavahi-client3 libavahi-common3
sudo systemctl enable --now avahi-daemon
export CARISMA_NDI_LIBRARY=/actual-path/libndi.so.6
python3 diagnose_ndi.py
python3 server.py --host 0.0.0.0 --port 8787
```

Options `--ndi-library` and `--ffmpeg` also accept paths. Open `http://SERVER-IP:8787` and use the private administrator key in `data/access.key`. Initial testing runs in the foreground; no 24/7 systemd service is installed automatically.

For a historical 0.3 upgrade, extract into a new folder and copy `data/` only while the server is stopped. File-HTML demo projects live in browser storage: export/import JSON and transfer media separately. `demo_compatta.html` now shares the full console.

## Check playback

1. Open **Ingressi NDI** and run **Apri test locale / NON NDI**. Moving video verifies encoding/browser playback only; audio starts muted.
2. Start a real transmitter, search sources, choose **Prova video**, then **Crea contenuto**.
3. Assign it to a screen and open its player. Enable audio only where needed.

Manual sources use the exact advertised name, e.g. `PC-REGIA (Programma)`, not `ndi://`. Verify that the source application actually outputs NDI.

| Profile | Video target | Audio |
|---|---|---|
| Light | 640×360, 15 fps, 800 kbit/s | AAC stereo, 48 kHz, 128 kbit/s |
| Standard | 1280×720, 25 fps, 2.2 Mbit/s | Same |

Bitrates are targets. Input keeps aspect ratio; frame-sync resamples audio and may supply silence. Measure AV sync, CPU and temperatures before adding streams or 720p. No hardware encoder acceleration is implemented. HX/HX3/H.265 discovery does not guarantee decoding; runtime/platform codecs determine support. Start with a known High Bandwidth source.

## Network, fallback and storage

Runtime operation is local, without CDN, cloud authentication or public STUN/TURN. With Internet absent but LAN present, normal operation can continue. Without LAN/server/live signal, an open player uses its cached fallback and retries; schedules remain local. Wait for cache readiness before disconnecting. Plain LAN HTTP browser cold-start offline is not guaranteed; service workers need localhost/HTTPS. No Chromecast firmware or bootloader is changed.

Prefer Ethernet and one subnet/VLAN initially; check mDNS/Avahi and scoped firewall rules. Extra discovery hosts:

```sh
python3 server.py --host 0.0.0.0 --ndi-extra-ips 192.168.1.10,192.168.1.11
```

Gateway-player HTTP defaults to 8787; raw FFmpeg input sockets bind loopback only. Control APIs require `X-Control-Token`; paired players have scoped credentials. Trusted LAN only; no Internet exposure or production multiuser/TLS certification.

`data/live/` is a rolling temporary segment window, not a recording. Old segments are removed; idle gateways stop after about 60 s. Exclude it from media backups. `encoder.log` is per-run diagnostics, not industrial log rotation.

## Test and licenses

```sh
python3 -m unittest discover -s tests -v
```

Encoding tests need FFmpeg; fake ABI tests need a C compiler. `tests/fake_ndi.c` is not NDI and must never be installed as a production runtime. See [QA_REPORT_v0.4.md](QA_REPORT_v0.4.md), [current report](TEST_REPORT.md) and [SOURCES.md](SOURCES.md).

NDI(R) is a registered trademark of Vizrt NDI AB. Its runtime is proprietary and subject to SDK/runtime terms; FFmpeg/codecs retain their licenses. No vendor binary is included. Download official distributions and review applicable commercial/distribution terms.

## References

- https://ffmpeg.org/download.html
- https://ndi.video/for-developers/ndi-sdk/
- https://ndi.video/
