# Prompt — historical 0.7 guide

Scripts synchronize in full; players scroll locally from the last state during LAN/server loss. First synchronization needs the server. Validate PRIMARY/BACKUP before show use. Current layout uses a fixed virtual page; current background USB support is in [CONTROLLERS.md](CONTROLLERS.md). Historical keyboard control below requires Prompt focus.

## Install and scripts

Stop/back up the 0.5.2 installation, merge the 0.7 patch beside `server.py`, and retain `data/`, `bin/`, `.setup/`, `Config_Locale.bat`. Start `Avvia_Server_LAN_Windows.bat` or `Avvia_Server_LAN_Linux.sh`, then open `/prompt.html`. Prompt tables share the existing SQLite database.

Import TXT/DOCX. A cue targets the following line:

```text
[[CUE: SCENA BALCONE]]
```

Three presets each: classic/wide/serif font, medium/large/extra-large size, white-on-black/amber-on-black/black-on-white colors. Reading line: 38%. Original 0.7 used viewport-height coordinates; 0.9+ uses the shared 1280×720 virtual page described in README.md.

| Action | Keyboard shortcut |
|---|---|
| PLAY/PAUSE | Space |
| Previous/next cue | Left/Right |
| Jog backward/forward | J/L |
| Blackout / TOP | B / Home |
| Forward shuttle zones | 1–5 |
| Center / STOP | 0 |
| Reverse shuttle zones | Shift+1–5 |

Shortcuts are ignored in text fields. Historical vendor-driver profiles map five buttons to Space/Left/Right/B/Home, jog to J/L, and ring to those shuttle keys. Wired jog/shuttle devices with exportable profiles were recommended; Contour driver compatibility needed workstation testing. Current direct HID service does not require keyboard emulation or page focus.

## OSC / QLab

UDP default: 9000. LAN startup exposes the listener; normal local startup binds loopback. Optional `Config_Locale.bat` settings:

```bat
set "CARISMA_PROMPT_OSC_PORT=9000"
set "CARISMA_PROMPT_OSC_ALLOW=192.168.1.50"
```

Replace example IPs; allowlist accepts comma-separated trusted addresses. In QLab configure a UDP Network Output Patch to the server, then custom OSC Network Cues:

```text
/carisma/prompt/play
/carisma/prompt/pause
/carisma/prompt/toggle
/carisma/prompt/stop
/carisma/prompt/speed 0.12
/carisma/prompt/speed/delta 0.02
/carisma/prompt/jog 0.10
/carisma/prompt/top
/carisma/prompt/cue/<id>
/carisma/prompt/cue "id"
/carisma/prompt/cue/next
/carisma/prompt/cue/prev
/carisma/prompt/blackout 1
/carisma/prompt/message "5 MINUTES"
/carisma/prompt/message/clear
```

Prefer absolute named cues (`/carisma/prompt/cue/scena-balcone`) to relative next/previous: duplicate UDP delivery cannot advance an absolute cue twice. UDP does not acknowledge delivery; retain manual override. Optional administrator firewall rule, replacing the example QLab address:

```powershell
New-NetFirewallRule -DisplayName "Carisma Prompt OSC" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 9000 -Profile Private -RemoteAddress 192.168.1.50
```

## Backup and acceptance

Pair PRIMARY and BACKUP separately. Both receive the full script/state; readiness reports online state, script version and position delta. A second authorized console can control the server. Use separate players, power supplies and Ethernet, preferably UPS; provide two stage monitors or manually switchable HDMI inputs. Shared SD/power/HDMI defeats redundancy. Keep a spare keyboard/controller.

The Raspberry generator offers Signage or Prompt; Prompt includes its page on SD and retains identity/script. Physical boot, Chromium cache after power loss, HDMI/video acceleration and SD reliability remain unverified.

Test at least ten cues: play/pause, jog, forward/reverse speeds, blackout and absolute OSC. Disconnect PRIMARY LAN while scrolling; check BACKUP readiness and reconnection, then repeat on actual Raspberry and under power loss. Run extended rehearsal and retain an emergency script copy. API/parser/loopback OSC results, not physical-stage certification: [QA_PROMPT_v0.7.md](QA_PROMPT_v0.7.md).
