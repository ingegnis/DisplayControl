# Interface guide

Screenshots show the current interface with disposable demonstration data in local Chrome. All connected players are browser instances, not physical panels. No real controller, NDI source or Chromecast validation is implied. Guides are in English; interface labels remain Italian.

## Screen console

Create players, select destinations and assign content from **Schermi**. Open **Monitor schermi** to inspect player previews.

![Screen console with four demonstration destinations](screenshots/console-screens.png)

## Screen monitor

The default view contains the panel matrix and **More**. Player names, preview age, unreachable/fallback states and errors remain visible. **More** reveals the header, statistics, filters, refresh/column selectors, pause/fullscreen commands and explanations; **Less** hides them again. Every reload starts with the matrix. Collapsing controls does not pause monitoring.

![Default screen monitor: matrix and More](screenshots/monitor-matrix.png)

![Expanded screen monitor controls](screenshots/monitor-more.png)

On narrow screens the matrix uses one column; the same **More** button opens the controls.

![Mobile monitor matrix](screenshots/monitor-mobile.png)

## Content library

Use **Contenuti** for clocks, graphic pages, local media and live-source entries.

![Content library](screenshots/console-contents.png)

## Playlists and schedules

Build ordered content in **Playlist**, then assign weekly rules in **Palinsesti**. Manual overrides retain priority until the operator resumes the schedule.

![Playlist editor overview](screenshots/console-playlists.png)

![Weekly schedules](screenshots/console-schedules.png)

## NDI inputs

**Ingressi NDI** reports installed dependencies, discovery and gateway streams. This capture has no real NDI runtime/source. The local **NON NDI** generator tests the encoding/browser path only. See [NDI setup](../LEGGIMI_NDI.md).

![NDI input page with actual dependency status](screenshots/console-ndi.png)

## Diagnostics

**Diagnostica** distinguishes browser connectivity from integrations that still require device testing.

![System and player diagnostics](screenshots/console-diagnostics.png)

## Organization settings

In **Impostazioni**, set the organization name, upload a logo and optionally apply the suggested colors. Backup/export controls are on the same page.

![Organization branding and project settings](screenshots/console-settings.png)

## Prompt console and player

The console edits TXT/DOCX scripts, selects cues and controls speed/blackout/messages. A paired player renders the same virtual page. These captures show a synthetic rehearsal script and a browser PRIMARY.

![Prompt console and script controls](screenshots/prompt-console.png)

![Prompt player with the demonstration script](screenshots/prompt-player.png)

The **Controller USB** panel generates the service pairing code and reports connections. The captured state is unpaired; it is not evidence of USB hardware testing. See [CONTROLLERS.md](../CONTROLLERS.md).

![USB controller pairing and status panel](screenshots/prompt-controllers.png)

## Signage pairing and output

From **Collega player fisici**, choose a screen and generate a one-use code. On the player open `/connect.html`, enter it, and wait for the first synchronization. Screenshots omit active pairing codes; the listed devices are demonstration browser players.

![Player pairing administration without an active code](screenshots/player-pairing.png)

![Browser pairing form](screenshots/player-connect.png)

![Paired signage browser output](screenshots/signage-player.png)

## Reproduce

The optional development runner uses real HTTP navigation, disposable server data and native browser storage:

```sh
python -m pip install playwright
python tests/browser_docs_check.py --capture-dir docs/screenshots --report browser-docs-results.json
```

Installed Google Chrome is required. Playwright is a development dependency only. The runner checks matrix/More behavior, keyboard access, responsive layout, refresh/filter/column controls, pause/resume, failure/recovery and pairing without an administrator key on the player. It never uses the installation's `data/` directory.
