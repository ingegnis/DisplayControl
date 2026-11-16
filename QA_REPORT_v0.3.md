> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Verifiche v0.3.0

## Ambiente e limiti delle prove

La navigazione verso file e URL e bloccata dal Chromium gestito di questo ambiente.
Per i test visivi e funzionali il codice HTML/CSS/JS e stato iniettato in pagine
vuote, con vere finestre popup e un adattatore di test per URL, localStorage e
snapshot IndexedDB in memoria. Nessun adattatore e presente nei file consegnati.
Questo verifica rendering, flusso comandi, isolamento e temporizzazioni, ma NON
certifica popup, storage su disco, permessi o riavvio offline nel browser dell'utente.
La persistenza browser reale e il caricamento degli HTML da file/HTTP devono essere
collaudati sul PC scelto. Per questa ragione non viene dichiarato un test end-to-end
completo del trasporto HTTP dal browser. Il backend Python e stato testato realmente
via HTTP localhost, senza adattatori.

## Backend Python

6 test unittest superati: autenticazione, heartbeat, payload non validi, conflitti
revisioni, persistenza SQLite dopo riavvio, upload/hash/download. Nessun pacchetto
Python di terzi necessario per il server.

## Console completa (browser con adattatori di test)

- Full console creates and selects a new named player
- Separate player renders assigned animated clock
- Full console assignment reaches player window
- Full player isolates assignments during offline simulation and catches up
- Hidden full player controls are accessible again
- Repeated opening reuses existing player window
- No external calls or JS errors (browser test adapters active)

## Demo compatta (browser con adattatori di test)

- Create a fifth named player, choose theme and select it
- Open player as separate browser window with working animated clock
- Live command from controller updates separate window
- Offline simulation freezes last received program, not incoming commands
- Reconnecting applies queued assignment
- Scheduled change executes while simulated link is down
- Offline clock seconds continue updating
- Fullscreen and hide/reveal controls work
- Two independent player windows receive distinct assignments
- Closing controller leaves independent player and clock running
- Reopened controller rejoins player through shared local test storage
- Blocked popup exposes help and direct player link
- User-provided names safely escaped
- Responsive 390-pixel layout has no horizontal overflow
- No external requests or JavaScript errors in the injected-browser harness

## Limiti invariati

- Player browser, non APK Android TV e non decoder Chromecast nativo.
- Nessun ricevitore o gateway NDI implementato.
- La demo compatta usa contenuti integrati, non carica video reali.
- La console completa mantiene gli upload e i palinsesti della versione precedente.
- Le anteprime della console non sono catture dello schermo remoto.
- Fullscreen, popup, browser mobile, tab in background e file locali sono soggetti
  alle impostazioni del browser e richiedono una verifica sul PC di destinazione.
- HTTP LAN del server non cifrato: usare solo una rete fidata, non esporre a Internet.
