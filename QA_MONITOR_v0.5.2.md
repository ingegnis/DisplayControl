> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Carisma v0.5.2-alpha - rapporto di collaudo

## Prove concluse

- 93 test Python completati, nessun errore o failure. Comprendono 75 test di
  regressione e 18 test nuovi per monitoraggio e autorizzazioni.
- 17 controlli JavaScript della policy latenza e coerenza copie player.
- 30 controlli Java desktop NetworkPolicy (NON un collaudo dell'Activity Android).
- Sintassi JavaScript di monitor.html, index.html, player.html, demo_compatta.html.
- 14 verifiche browser monitor con quattro player di prova, API e server veri,
  conversione e video FFmpeg reali, miniature JPEG reali generate via Canvas.

## Test browser monitor (log originale)

- Player captures a real decoded FFmpeg video frame; clock marked as reconstructed
- No thumbnail demand before opening monitor
- All four authenticated players upload actual JPEG previews and monitor displays them
- Monitor opens no new NDI receiver or FFmpeg encoder
- Refresh selector 1, 2, 5 seconds updates server lease
- Group filter hides unrelated screens
- New content confirmed by player replaces previous thumbnail
- Actual fallback rendering is reported and marked in monitor
- Mobile 390px has no horizontal overflow
- Disconnected player retains stale image with age and unreachable status; not fake live
- Player reconnection restores fresh preview
- Pause releases monitoring demand without stopping player playback
- Resume re-enables monitoring
- No JavaScript page errors

## Dimensioni JPEG osservate, non un limite di traffico garantito

- foyer-ingresso: 8413 byte / rendered
- ingresso-sala: 7308 byte / rendered
- camerini: 7379 byte / frame
- bar-foyer: 7366 byte / rendered

Le grafiche sono ricostruzioni etichettate, non screenshot del DOM. Il video e
un generatore locale testsrc2, non una sorgente NDI fisica.

## API e sicurezza

Testati: accesso amministratore, divieto lettura ai player, upload limitato
all'identita abbinata, revoca, nuovo abbinamento, schermo eliminato, token non
esposti, JPEG limitato per dimensione e risoluzione, input invalidi, frequenza
massima, una sola immagine conservata, scadenza della richiesta di monitoraggio,
piu monitor con intervalli diversi e arresto senza interrompere il player.

## Latenza

La patch include la policy v0.5.1 Reattiva. Il confronto gia completato in questo
ambiente con Stabile dava 1,807 s -> 0,632 s di coda media del player. I log
qa_v051/latency-*.json e QA_LATENZA_v0.5.1.md restano inclusi. Queste misure NON
sono una nuova misura con il monitor aperto e NON sono la latenza sorgente-schermo.
Il nuovo test verifica che il monitor non crea ulteriori encoder. La regressione
Python ricontrolla frammenti, keyframe e decodifica della pipeline FFmpeg.

## Ambiente e limiti

Chromium/Linux con set_content, un ponte esplicito alle vere API HTTP e storage
in memoria per IndexedDB/localStorage. Non viene aggirata la policy del browser
che impedisce la normale navigazione HTTP nell'ambiente. API, FFmpeg, frame video,
JPEG e DOM sono reali; questa fixture NON certifica navigazione/persistenza sul PC,
rete del teatro, Windows, NEXCOM, Android o riavvio fisico offline.

Non verificati: trasmettitore NDI dell'utente, latenza end-to-end, resa audio,
TV/HDMI, app Android compilata, temperature o uso continuativo 24/7. La conferma
che il precedente player e lo stream NDI funzionano sul PC e fornita dall'utente,
non osservata da questo ambiente.

Una prima esecuzione monolitica e stata interrotta dal runner prima della fine;
non e stata contata come riuscita. E stata poi completata un'altra esecuzione
con 93 test OK (qa_v052/python-tests-final.log, durata 40,412 s). Il dump
faulthandler al secondo 40 in quel log era diagnostico, durante il teardown:
la suite ha concluso regolarmente. Nessuna asserzione fallita e stata ignorata.

## Ripetere le prove

```sh
python -m unittest discover -s tests -v
node tests/test_live_policy.js
# Ambiente di sviluppo con Playwright/Chromium, non necessario in produzione:
python tests/browser_monitor_check.py
```

I test del monitor non richiedono Internet. Il video di prova richiede FFmpeg.
Le dipendenze di test del browser non vengono aggiunte al server di produzione.
