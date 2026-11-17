# Raspberry Pi player — installer 0.11-r1

Prepared for the user's Raspberry Pi 3B+. Supports one Prompt or Signage station per Raspberry. The application shell is 0.11.0-alpha, compatible with the 0.11 Core/coordinator. This is an application installer over Raspberry Pi OS Desktop, not an SD image or replacement OS.

Installer generation, preservation boundaries and the existing HTTP player have automated tests. No physical Raspberry was available: ARM package installation, graphical boot, HDMI/audio, acceleration, thermals and power-loss durability still require the checks below.

## 1. Prepare the 3B+ and SD

You need the Pi, suitable power supply, microSD, a **full-size HDMI cable** for the 3B+, a display, Ethernet cable and initially a keyboard/mouse. Use Ethernet for the first rehearsal. PRIMARY and BACKUP require separate Raspberry units, SD cards and power supplies; a single Pi is one player.

1. On your PC install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select **Raspberry Pi 3** and **Raspberry Pi OS with desktop**. For this 1 GB device, start with the current **32-bit Desktop** image as a conservative memory choice; 64-bit Desktop is also supported by this Python/browser installer. **Do not select Lite, Full, or the x86 PC image.** A working Bookworm Desktop installation with Python 3.11+ can also be used without reimaging.
3. Set a unique hostname such as `prompt-primary`, username/password, Europe/Rome timezone and keyboard layout. Optionally enable SSH and configure Wi-Fi. Do not assume the account is named `pi`.
4. Write the selected SD. **Imager erases that card: check the selected destination and save any existing data first.**
5. Insert the SD, connect HDMI/Ethernet and power on. Complete the desktop setup. Open a terminal on the Pi as the account that will log in at boot.

Official references: [OS downloads, including 32/64-bit Desktop](https://www.raspberrypi.com/software/operating-systems/), [kiosk startup](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/), [desktop configuration](https://www.raspberrypi.com/documentation/computers/configuration.html). The 32-bit choice and 720p baseline here are project preparation choices, not measured performance guarantees.

## 2. Download and install

Internet is needed for this download and any missing apt packages. After setup the player uses the local show network; it does not require GitHub at runtime. The archive contains the runtime and installer, not Chromium/OS packages.

On the **Raspberry terminal**, run:

```sh
mkdir -p ~/Downloads/displaycontrol-rpi
cd ~/Downloads/displaycontrol-rpi
curl -fL -o DisplayControl_Raspberry_v0.11-r1.tar.gz https://github.com/ingegnis/DisplayControl/releases/download/raspberry-v0.11-r1/DisplayControl_Raspberry_v0.11-r1.tar.gz
curl -fL -o DisplayControl_Raspberry_v0.11-r1_SHA256.txt https://github.com/ingegnis/DisplayControl/releases/download/raspberry-v0.11-r1/DisplayControl_Raspberry_v0.11-r1_SHA256.txt
sha256sum -c DisplayControl_Raspberry_v0.11-r1_SHA256.txt --ignore-missing
tar -xzf DisplayControl_Raspberry_v0.11-r1.tar.gz
cd DisplayControl-Raspberry
sh Install_Raspberry_Player.sh
```

Continue only if the archive checksum says **OK**. If `curl` is missing, install it with `sudo apt-get update` and `sudo apt-get install curl`. Alternatively download the archive/checksum with Chromium or copy them from your PC/USB stick; verify before extraction.

The wizard asks for:

| Question | Answer |
|---|---|
| Server/coordinator URL | e.g. `http://192.168.1.20:8787` — replace with the actual regia/coordinator address |
| Mode | `1` Prompt; `2` Signage |
| Dependencies | Accept to install/update Chromium, Python and fonts through apt; sudo asks for the Pi user's password |

Use the **coordinator** URL when Core A/B failover is configured. Never enter `localhost`, the Raspberry address, the GitHub URL, an admin token or a URL ending in `/prompt.html`. The coordinator and Core addresses must be stable/reserved on your LAN. The examples are placeholders, not your saved network settings.

For explicit installation without the questions:

```sh
sh Install_Raspberry_Player.sh --server http://192.168.1.20:8787 --mode prompt --install-deps
```

For Signage replace `prompt` with `signage`. Run **without sudo** as the desktop user; the installer elevates only apt. Do not run two installers at once. To inspect the plan without writing files or running apt/services:

```sh
sh Install_Raspberry_Player.sh --server http://192.168.1.20:8787 --mode prompt --dry-run
```

If installing over an old `prepare_kiosk.py` setup, first stop its service and rename `~/.config/autostart/displaycontrol-kiosk.desktop` to a name that does not end in `.desktop`; retain its old private configuration. The new installer refuses this legacy autostart to avoid two browser launches. Existing managed service files can be migrated only after preserving their data; otherwise use a fresh Desktop user.

## 3. Desktop boot and screen

In Raspberry Pi's Control Centre / Raspberry Pi Configuration (names vary by OS release):

- Enable **boot to Desktop** and **desktop auto-login** for the same account that ran the installer.
- Disable **Screen Blanking** and any screen lock/sleep timer. Do not disable system sleep/idle by killing unrelated desktop services.
- In screen settings select the connected HDMI display and start at **1280×720, 60 Hz** if offered. Use landscape for initial testing. Change rotation/resolution with OS screen settings; Prompt mirroring is configured in DisplayControl.
- For Signage audio, select the actual HDMI/audio output and set the desired volume in OS settings.

If needed run `sudo raspi-config` and use the equivalent interactive boot/display options. The installer does not silently change OS login, Wi-Fi, firewall, HDMI firmware or reboot the Pi.

Then run:

```sh
sudo reboot
```

The local station starts as a user service. A supervised Chromium kiosk starts when the desktop loads. The installer registers both labwc and desktop autostart; a local lock ensures only one supervisor owns the dedicated browser. Chromium uses its own persistent profile; it does not touch your normal browser profile. The launcher waits for the local shell rather than waiting for the remote Core, so an outage does not prevent cached content from opening.

## 4. Pair the player

**Prompt:** on the regia PC open Prompt control through the coordinator URL. Generate a player pairing code for **PRIMARY** or **BACKUP**. On the Raspberry's pairing screen enter a recognizable device name and that code. The role is assigned by regia pairing, not by the installer. Use a separately generated BACKUP code on the second unit.

**Signage:** in the regia console create/select the panel, open **Connect physical players**, select that panel and generate its eight-digit code. Enter the code on the Raspberry. Assign a clock/image first, then a small local video.

No administrator key is needed on the Pi. Leave the LAN connected until script/media synchronization and cache readiness complete. Pairing and show media remain private on that Pi; do not commit or share its data directory.

## 5. Check before today's rehearsal

1. Reboot and confirm that the player returns without a keyboard, manual login or code re-entry.
2. Prompt: load a short script, scroll, pause, change speed and select a cue. Check reading line and fonts against regia. Let it run at least 15 minutes to expose screen blanking or power/thermal issues.
3. Signage: check a clock/image, then one short video and HDMI audio. On the 3B+, begin at 720p and simple content. NDI processing remains on the Core; the Pi still has to decode the resulting browser video. No 1080p/high-bitrate/low-latency performance guarantee is made.
4. After synchronization, unplug Ethernet temporarily. The cached show should remain available; live NDI cannot continue without its source/network. Reload/reopen the local player and verify recovery with the actual media. Restore Ethernet.
5. Restart the local service and reboot the Pi normally. Confirm pairing/cache retention. Test actual power interruption only after backing up the show and when the unit is not in use; SD durability is not certified.
6. With the configured cluster, stop Core A and verify control returns via B without changing the player's coordinator address. Coordinator loss still prevents new commands after lease expiry; open players retain available local playback.

Keep an emergency script copy. PRIMARY/BACKUP are logically separate; TAKE does not physically switch HDMI. Do not rely on unattended show use until these checks pass on each unit.

## 6. Daily controls and troubleshooting

Run as the same desktop user, from a terminal or SSH:

```sh
~/.local/share/displaycontrol-player/manage.sh status
~/.local/share/displaycontrol-player/manage.sh stop
~/.local/share/displaycontrol-player/manage.sh start
~/.local/share/displaycontrol-player/manage.sh restart
systemctl --user status displaycontrol-station.service --no-pager
systemctl --user restart displaycontrol-station.service
journalctl --user -u displaycontrol-station.service -n 40 --no-pager
```

`stop` pauses the browser persistently, including across reboot; the local service continues. `start` clears that pause; if the desktop supervisor is absent, log out/in or reboot. `restart` restarts only the dedicated browser; it does not erase pairing/cache. Browser crash recovery does not imply detection of a renderer/GPU freeze. A browser that is frozen while its process remains alive can be restarted with this command.

| Symptom | Check |
|---|---|
| Desktop appears, no player | Desktop auto-login user, `manage.sh status`, then `start` and reboot. Do not launch kiosk from an SSH shell without a graphical session. |
| Pairing page remains | Coordinator URL/LAN, code expiry, PRIMARY/BACKUP or selected panel. Generate a new code; never paste admin credentials. |
| Blank/black display | HDMI input/cable, OS display settings, assigned content, and browser status. Hardware power/input state is outside the app. |
| Screen sleeps | Disable Screen Blanking/lock in OS settings and in the display's own settings. |
| Stuttering/slow video | Start with 720p, one tab/player; check power, heat, free RAM and Ethernet. `free -h`; if available `vcgencmd get_throttled` and `vcgencmd measure_temp`. |
| No user systemd bus | Log in as the intended desktop account locally, then rerun. Do not run installer/systemctl as root. |
| Interrupted apt/install | Fix the reported package/network error and rerun the same installer; no wipe/reinstall of private data is needed. |

Supervisor log: `~/.local/share/displaycontrol-player/data/kiosk.log`, rotated to at most three 512 KiB files. Browser stderr is discarded to avoid persisting request URLs/tokens. Service diagnostics do not print pairing credentials; still review logs before sharing.

## 7. Updates, changing pairing and removal

Application files are copied to content-named `releases/` directories under `~/.local/share/displaycontrol-player`. `data/station.json` holds the private scoped pairing identity, and `data/browser/` holds Chromium's profile and cached media. Existing startup files are backed up under `backups/`. Retain the whole private installation folder for recovery; back it up only with the browser and station stopped and store that backup privately.

To update, stop the kiosk with `manage.sh stop`, extract the new approved bundle, rerun the installer with the **same server, mode and port**, then run `manage.sh start` and reboot. Pairing/cache remain. Old application copies are retained. Do not apply updates during a show.

To intentionally change server or switch Prompt/Signage, revoke the old identity in regia if possible, then stop the browser and station and move the old data aside (preserving it):

```sh
~/.local/share/displaycontrol-player/manage.sh stop
sleep 12
systemctl --user stop displaycontrol-station.service
cd ~/.local/share/displaycontrol-player
mv data "data-before-repair-$(date +%Y%m%d-%H%M%S)"
```

Run the installer again with the new server/mode; it creates fresh private state. Then `manage.sh start` and reboot. Pair with a new code. This intentionally creates a fresh browser cache; wait for synchronization again. Keep local port 8877 unless this is a separate, deliberately fresh installation.

To disable automatic operation while retaining all private content:

```sh
~/.local/share/displaycontrol-player/manage.sh stop
systemctl --user disable --now displaycontrol-station.service
```

The paused supervisor may still start at desktop login but opens no browser. To remove startup integration, remove only the generated `displaycontrol-player.desktop` and `displaycontrol-station.service` from your user configuration, and remove only the block between `# BEGIN DisplayControl player` and `# END DisplayControl player` in `~/.config/labwc/autostart`; keep other desktop commands. Run `systemctl --user daemon-reload`. Do not delete private data unless you deliberately want to erase pairing/cache.
