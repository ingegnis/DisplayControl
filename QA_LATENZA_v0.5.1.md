> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Carisma v0.5.1-alpha - rapporto verifica latenza

## Diagnosi sul codice precedente

Analizzati `ndi/gateway.py` e `CarismaLiveClient` negli HTML della v0.5-alpha
contenuta nel pacchetto consegnato. Rilevati `-hls_time 1`, GOP da 1 secondo,
posizionamento iniziale `end - 2`, polling ogni 500 ms e recupero solo con
buffer maggiore di 5 secondi. Questi parametri introducono attesa anche quando
la ricezione NDI funziona; non dimostrano che tutta la latenza riferita derivi
da quel solo tratto.

## Test completati sul codice consegnato

- 75 test Python passati (`python -m unittest discover -s tests -v`).
  Comprendono i 65 test precedenti e 10 nuovi test policy/segmentazione.
- 17 controlli JavaScript della policy, limiti numerici, recupero e coerenza
  delle copie player (`node tests/test_live_policy.js`).
- Sintassi JavaScript verificata con Node per index, demo_compatta e player.
- 11 controlli browser di regressione: abbinamento, UI, cambio contenuti,
  orologio, fallback, riconnessione, due player che condividono FFmpeg.
- FFmpeg reale: segmenti 360p e 720p della modalita Reattiva, e 360p Stabile.
  Verificati durata, keyframe iniziale, decodifica video/audio e metadati HLS.
- Prove di buffering riportate sotto, con ulteriori controlli di recupero
  dopo blocco artificiale del manifest di 5 s e pulsante Torna alla diretta.

Un errore di sintassi nel nuovo file di test e stato corretto prima della
riesecuzione completa; il risultato finale non ignora test falliti.

## Misure locali: cosa rappresentano

Generatore FFmpeg `testsrc2` + tono AAC, 640x360/15 fps, Chromium/Linux.
Confronto tra le modalita Stabile (tempi uguali alla v0.5) e Reattiva del nuovo
codice. Non e una cattura della tua sorgente NDI. Non e la latenza sorgente-schermo.

| Misura | Stabile | Reattiva |
|---|---:|---:|
| Coda media del player (50 campioni ogni 200 ms) | 1.807 s | 0.632 s |
| Coda minima osservata | 0.989 s | 0.334 s |
| Coda massima osservata | 2.378 s | 0.914 s |
| Prima riproduzione osservata dall'avvio della prova | 2.107 s | 0.871 s |
| Fotogrammi decodificati nell'intervallo campionato | 150 | 150 |
| Fotogrammi scartati dichiarati dal browser nell'intervallo | 0 | 0 |

La coda e `video.buffered.end(...) - video.currentTime`. La prima riproduzione
misura l'avvio della prova, non il ritardo di un'immagine. Nessun arresto e
stato osservato nei 50 campioni; questo non certifica la stabilita 24/7.
I dati grezzi sono in `qa_v051/latency-stable.json` e `latency-responsive.json`.

## Ambiente e limiti

La navigazione HTTP diretta del Chromium gestito e risultata bloccata con
`ERR_BLOCKED_BY_ADMINISTRATOR`; non e stata aggirata o modificata la policy.
Le prove UI usano `set_content` e un ponte esplicito verso le vere API HTTP
locali. Nella regressione lo storage e sostituito da memoria temporanea;
FFmpeg, i byte MP4, le API e la decodifica MediaSource sono reali.
Le richieste HTTP del server vengono inoltre collaudate dai test Python.

Non sono stati collaudati: runtime NDI proprietario reale, sorgente dell'utente,
LAN UniFi, Windows nativo, NEXCOM, Chromecast, audio percepito, labiale,
riavvio offline e lunga durata. Non e stata misurata la latenza NDI end-to-end.
Il funzionamento della tua precedente versione e stato riferito da te, non
osservato da questo ambiente.

## Modifiche principali

`ndi/gateway.py`: policy responsive/stable, keyframe e segmenti piu brevi,
policy comunicata al client. `server.py`: versione e opzione --live-mode.
Gli HTML del player: policy bounded, recupero arretrato, pulsante live,
etichetta che distingue coda e latenza totale. `sw.js`: nuova versione shell.
Nessuna nuova dipendenza runtime o migrazione dei dati utente.

## Documentazione tecnica di riferimento

```text
https://ffmpeg.org/ffmpeg-formats.html#hls-2
https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-recv
```

La documentazione FFmpeg distingue la durata dei segmenti dall'allineamento
ai keyframe. La documentazione NDI descrive le code del ricevitore e il
monitoraggio dei frame. I risultati numerici sopra provengono dai nostri
log locali, non da queste fonti e non sono una prestazione garantita.
