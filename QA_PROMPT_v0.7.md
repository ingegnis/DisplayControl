> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# QA Carisma Prompt v0.7-alpha

## Stato sintetico

Il nuovo motore Prompt e' stato verificato a livello API, database, pairing, parser, comandi, OSC e integrazione con le API dei player fisici esistenti. Non si dichiara collaudo su Raspberry, monitor palco, controller Contour o QLab reali.

## Test dedicati Prompt

Superati i test automatici per:

- parsing copione e cue `[[CUE: ...]]`;
- estrazione testo DOCX con librerie standard;
- rifiuto/normalizzazione delle impostazioni fuori dai 3 preset font/dimensione/colori;
- play, pausa, velocita', jog, cue, blackout e messaggi;
- pairing monouso PRIMARY/BACKUP e stato hot-backup;
- parsing OSC message e bundle;
- autenticazione API amministratore;
- API player con token separato e import TXT.

## Test listener OSC reale

E' stato avviato un listener UDP locale del modulo e inviato un vero datagramma OSC `/carisma/prompt/speed` con float. Il runtime ha ricevuto e applicato il valore e ha registrato mittente/indirizzo. Questa prova valida il listener UDP/codec, non una rete QLab reale.

## Regressione mirata

Dopo l'integrazione sono stati rieseguiti **32 test** combinati di server, player fisici e Prompt: tutti superati, compreso il test FFmpeg reale dei segmenti scoped. Sono stati poi rieseguiti separatamente **18 test del monitor** con `PYTHONPATH=tests:.`: tutti superati.

Totale regressione mirata di questa consegna: **50 test superati**. Non viene sommato a questo numero il precedente conteggio globale di versioni diverse.

## Controlli statici aggiuntivi

- Server avviabile con OSC disabilitabile o su loopback.
- Avvio LAN espone OSC su `0.0.0.0`, con allow-list IP opzionale.
- Player Prompt esegue lo scroll localmente con `requestAnimationFrame`.
- Poll di stato player impostato a 50 ms per ridurre il ritardo del comando; il rendering continua localmente fra un aggiornamento e l'altro.
- Controller USB usa scorciatoie keyboard standard; le zone reverse sono mappate tramite `Shift+Digit1..5`.

## Limiti non collaudati

- QLab reale -> rete fisica -> server Carisma -> display palco.
- Latenza end-to-end misurata con controller jog fisico.
- Driver Contour e profilo applicazione Windows.
- Boot e persistenza cache su Raspberry Pi 3 B/B+ reale.
- Recupero dopo blackout e corruzione SD.
- Switch HDMI / secondo monitor e failover fisico.
- Uso 24/7 e stress prolungato.

Prima di uno spettacolo, PRIMARY e BACKUP devono superare una prova sul posto con perdita LAN, perdita alimentazione, cambio ingresso e controllo manuale.
