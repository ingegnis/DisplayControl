# USB controllers — 0.10.0-alpha

The background service reads USB HID and sends scoped Prompt API commands. Prompt may be closed or unfocused; the server and service must remain running. This is a desktop process, not device firmware or a pre-login Windows service.

## Profiles

| Controller | VID:PID | Input | LCD |
|---|---|---|---|
| AJAZZ AKP03E | `0300:3002` | AKP 3, state reports | 6 keys |
| AKP03E alternate revision | `0300:1002` | AKP 2, discrete clicks | 6 keys |
| Mars Gaming MSD-TWO | `0b00:1001` | AKP 2, discrete clicks | 6 keys |
| Contour ShuttleXpress | `0b33:0020` | Shuttle, jog, 5 buttons | None |
| Contour ShuttlePRO v2 | `0b33:0030` | Shuttle, jog, 15 buttons | None |
| Elgato Stream Deck Neo | `0fd9:009a` | 8 keys, 2 touch buttons | 8 keys |

**Alpha profiles tested with synthetic reports and simulated USB only; no physical controller was available.** Detection checks USB identities and interfaces. Unknown devices and keyboards are ignored; other firmware/revisions need separate validation.

## Install and pair

Windows: run `Installa_Controller_Windows.bat`, generate a controller code in Prompt, then run `Configura_Controller_Windows.bat` with the Core address and code. Start `Avvia_Controller_Windows.bat` and connect a supported device.

macOS/Linux, Python 3.11+:

```sh
sh Installa_Controller_Linux_Mac.sh
sh Avvia_Controller_Linux_Mac.sh --setup
sh Avvia_Controller_Linux_Mac.sh
```

Installers isolate hidapi 0.15.0 and Pillow 13.0.0 in `.controller-venv/`. Pairing belongs to the service, not the device: existing `data/akp03e_controller.json` tokens are reused. Keep that file private. Legacy `*_AKP03E_*` launchers and `python akp03e_controller.py` forward to this service. Stop old instances before updating; an OS file lock prevents duplicate instances using the same configuration.

Close vendor apps to avoid interface conflicts and duplicate keyboard macros. Linux may need `99-displaycontrol-controllers.rules` installed in `/etc/udev/rules.d/`, followed by udev reload and reconnection. macOS may require HID permissions. Permissions are not changed automatically; no global keyboard hooks are used.

Optional Windows startup: `Installa_Avvio_Automatico_Controller_Windows.bat` reuses the legacy startup entry. Normal installation does not enable autostart.

## Swap and operate

Swap devices without restarting or pairing again. Discovery runs every second; failed opens retry after two seconds. Actual connection time depends on OS, interface availability and LCD updates. Up to eight supported interfaces can coexist; commands execute serially.

Connecting does not start or stop scrolling; unplugging leaves it running. Centering a Contour ring sends STOP. A ring connected off-center must return to center before arming. The console's **Controller USB** status excludes USB paths and serial numbers.

| AJAZZ / MSD-TWO control | Action |
|---|---|
| LCD 1–6 | PLAY/PAUSE, previous cue, next cue, blackout, TOP, TAKE A/B |
| Encoder 1 | Speed; press PLAY/PAUSE |
| Encoder 2 | Jog; press STOP |
| Encoder 3 | Previous/next cue; press TAKE A/B |
| Side buttons 1–3 | Clear message, STOP, TAKE A/B |

Neo uses the same first six actions; LCD 7/8 decrease/increase speed, and touch buttons jog backward/forward. Images are 96×96 JPEG; InfoBar is unchanged.

Contour ring: seven speeds per direction, STOP at center; inner wheel: jog. Buttons 1–5: PLAY/PAUSE, cue −, cue +, blackout, TOP. PRO v2 buttons 6–9: TAKE, clear message, STOP, TAKE; 10–15: PLAY, PAUSE, STOP, speed −, speed +, TAKE BACKUP. Confirm physical numbering in diagnostics.

PLAY uses 0.11 virtual pages/s if STOP or a new script left speed at zero. PAUSE preserves speed; encoder increments are unchanged.

## Diagnose before use

Stop the service and run `Test_Controller_Windows.bat`, or:

```sh
sh Avvia_Controller_Linux_Mac.sh --list
sh Avvia_Controller_Linux_Mac.sh --diagnose --seconds 30
```

Diagnostics read events without server commands. Check every control, ring centering, LCD orientation and reconnection. Then test with Prompt closed and a player running a rehearsal script.

## Resilience and limits

Bounded queues expire commands after 750 ms; STOP has priority. Events from an old connection cannot affect a new generation. USB reading, commands and telemetry run separately. An HTTP request already in progress can delay the next command: STOP is not a real-time hardware emergency stop.

Per-Core tokens and fallback retain 0.9 behavior: ambiguous HTTP results do not replay relative commands; HTTP refusals do not fall back to OSC. UDP has no delivery acknowledgement. Endpoint switching does not replicate Cores.

Tests cover protocols and a single-pairing swap through real loopback HTTP. Physical USB, firmware, vendor-driver conflicts, macOS/Linux permissions, display orientation and stage latency remain unverified. See [TEST_REPORT.md](TEST_REPORT.md).

## Protocol references

Independent implementation; no external driver is bundled or executed. References consulted 2026-11-16; their authors do not certify this integration.

## References

- https://marsgaming.eu/en/control-decks/msd-two
- https://github.com/tommybobb/crabdeck/blob/master/devices.py
- https://github.com/tommybobb/crabdeck/blob/master/deck.py
- https://github.com/4ndv/mirajazz/blob/main/src/state.rs
- https://github.com/LinuxCNC/linuxcnc/blob/master/src/hal/user_comps/shuttle.c
- https://github.com/abcminiuser/python-elgato-streamdeck/blob/master/src/StreamDeck/Devices/StreamDeckNeo.py
- https://github.com/abcminiuser/python-elgato-streamdeck/blob/master/src/StreamDeck/ProductIDs.py
