# Device preparation checklist — 0.11

Prepare one small rehearsal system before connecting the complete installation. This is an installation checklist, not evidence of physical device testing.

| Role | Software | Connections |
|---|---|---|
| Regia / coordinator PC | `coordinator.py`, browser console, USB controller service | LAN to switch; chosen controller by USB |
| Core A | `server.py` with Core A cluster configuration | LAN, separate power; FFmpeg/NDI runtime if needed |
| Core B | Same application with Core B configuration | LAN and separate power; same live dependencies |
| Prompt PRIMARY | Browser and `player_station.py --mode prompt` on Raspberry/PC | LAN to switch; HDMI to PRIMARY monitor |
| Prompt BACKUP | Independent local station, separately paired | Separate LAN/storage/power; HDMI to BACKUP monitor |
| Signage panel | Browser station or Android TV player | LAN/Wi-Fi to local network; HDMI to TV |
| Optional source PC | Real NDI transmitter | LAN to switch; decoding/encoding stays on active Core |
| Optional QLab Mac | OSC Network Cues | LAN to coordinator UDP 9000, with relay configured |

Use one of AJAZZ AKP03E, Contour ShuttleXpress/PRO v2, Mars Gaming MSD-TWO or Stream Deck Neo. It plugs into the regia PC, not the switch. Close vendor applications; start the unified service. Prompt may be closed or unfocused. Physical profiles still need diagnostic verification on the exact firmware.

## 1. Software and network

- Download the current full source package, or apply the cumulative patch with server/controller processes stopped. Back up `data/` privately first.
- Reserve stable LAN addresses for the regia/coordinator and both Cores. Keep clocks synchronized. Do not expose these services to the Internet.
- Follow [CLUSTER.md](CLUSTER.md) to generate and distribute the three private configurations. Keep Core A's existing show data; Core B is overwritten by the authoritative private copy.
- Start the Cores and coordinator. Open the coordinator URL; confirm active Core and both replicas in **SHOW PACKAGE**. Default HTTP port is 8787 on each separate host; local station port 8877 binds localhost only.
- If using OSC, configure coordinator UDP 9000, Core UDP 9001 and narrow sender allowlists. No firewall rules are changed automatically.

## 2. Show and controls

- Export a [SHOW PACKAGE](SHOW_PACKAGE.md) from the current show. Import/preview/activate through the coordinator; confirm script, cues, logo/colors, media, playlists, schedules and screen definitions.
- Install and pair the [USB service](../CONTROLLERS.md) against the coordinator URL. Check every button/encoder, display orientation, disconnect/reconnect and operation with Prompt closed.
- Run PRIMARY/BACKUP [local stations](PLAYER_STATION.md), using separate codes and roles. Wait for the full script/cache and verify font availability and matching reading lines.
- Pair one signage browser, start with a clock/image, then local video. Chromecast requires an APK build and actual device installation; source/desktop Java tests do not certify it.

## 3. Failure rehearsal

- Start Prompt scrolling; stop Core A and observe Core B promotion and recovered control through the same coordinator URL. Check retained pairing and no repeated relative commands.
- Change a cue/message on B, restart A and verify it catches up without taking over.
- Stop the coordinator: after lease expiry new commands must stop, while synchronized open players keep their local program. Restore the coordinator and verify recovery.
- Isolate a local station from the LAN, reload its page and restart its local service. Then repeat with real power interruption; browser process tests do not certify SD durability or physical boot.
- For NDI, compare the local non-NDI generator with the real source, then test signal loss/recovery, audio, delay, CPU/temperature and load. NDI pipelines may restart during Core failover.

Use separate power/storage for PRIMARY/BACKUP. TAKE changes only the logical output role; arrange two monitors or an external/manual HDMI switch. Keep an emergency script copy and record results for each physical unit before show use.
