# Test DisplayControl 0.10.0-alpha

Eseguiti il 16 novembre 2026 su Windows x64, Python 3.14.7, Node.js,
hidapi 0.15.0, Pillow 13.0.0, FFmpeg/ffprobe e compilatore Visual C.

## Esito attuale

- **151 test Python: 0 errori, 0 fallimenti, 0 saltati**, inclusi 24 test del nuovo hub.
- Tre suite JavaScript superate e sintassi di 20 script verificata.
- Installazione da zero in un ambiente Python isolato completata; avvio compatibile
  `akp03e_controller.py --list` riuscito con il nuovo servizio.
- Enumerazione HID reale: **0 controller supportati collegati**.

| Area | Verifica | Portata |
|---|---|---|
| Identificazione | VID/PID, interfacce, esclusione di tastiere/dispositivi sconosciuti | Metadati sintetici |
| AJAZZ | Encoder, pulsanti, firma ACK, entrambe le identità AKP03E | Report sintetici |
| MSD-TWO | Protocollo 2, clic senza fronte di rilascio, LCD e padding | Report e trasporto HID simulati |
| Contour Xpress/PRO v2 | Ghiera firmata, ritorno al centro, jog con wrap, pulsanti simultanei e mappa PRO estesa | Report sintetici |
| Neo | Otto tasti, due touch, fronti, immagini JPEG 96×96, pacchetti e feature brightness | Pillow reale, HID simulato |
| Scambio | AJAZZ → MSD-TWO → Contour → Neo senza pagina Prompt, con un solo pairing | API HTTP reale su loopback, USB simulato |
| Hot unplug | Vecchie code respinte dopo nuova generazione della connessione | USB simulato |
| Doppio avvio | Blocco del file di configurazione e rilascio alla chiusura | File lock Windows reale |
| Reattività | STOP prioritario, eventi scaduti, polling bloccato che non ferma il thread comandi | Test concorrenti con attese controllate |
| Riservatezza stato | Niente token, percorsi USB o seriali negli heartbeat del servizio | API e fixture |
| PLAY | Ripresa dopo STOP con velocità zero | API HTTP reale |
| Regressione | Server, pairing, token, revoca, Prompt, Monitor e player | Suite completa |
| FFmpeg | 360p/720p, frammenti, keyframe, accesso e decodifica audio/video | FFmpeg reale |
| NDI | Binding C, perdita/ripresa segnale e percorso di codifica | DLL ABI simulata; non è una sorgente NDI reale |
| Android | Policy, manifest e coerenza degli asset | Sorgenti; APK non compilato/eseguito |

La prova dell'API controller non apre alcuna pagina web e non genera scorciatoie
tastiera: verifica il percorso usato dal servizio esterno, indipendente dal focus.
Non certifica il comportamento di un driver USB reale o le autorizzazioni di un OS.

## Verifiche storiche

Il motore di sincronismo Prompt della 0.9 resta incluso. Le misure browser
800×600/1920×1080 e di arresto/riavvio sono conservate in
`test-results/browser-sync.json` come evidenze della **0.9**, senza attribuirle
a un nuovo collaudo fisico. Il precedente rapporto è nel tag GitHub `v0.9.0-alpha`.
Per la 0.10 i controlli JavaScript sono di sintassi e regressione automatica.

## Limiti

Nessun controller AJAZZ, Contour, Mars Gaming o Elgato fisico è stato disponibile.
Restano da verificare firmware, identificazione reale, pulsanti, LCD, numerazione,
orientamento, conflitti con software del produttore, hot unplug e latenza sul palco.
macOS/Linux non sono stati collaudati qui; verificare accesso HID e permessi udev.

Il riconoscimento automatico opera sugli identificativi documentati, non su qualunque
revisione dello stesso marchio. Un controller sconosciuto non viene aperto. Per
diagnosticare un'unità reale usare i comandi descritti in CONTROLLERS.md.

Il servizio deve essere avviato e il server deve essere raggiungibile per ricevere
nuovi comandi. La lettura USB è separata dalle richieste di rete. Le richieste HTTP
già in corso possono ritardare quelle successive; STOP non è un arresto hardware
in tempo reale. Scollegare un controller non ferma lo spettacolo; centrare la ghiera
Contour invia STOP. La deduplicazione riguarda il singolo Core e OSC non conferma
la consegna.

Nessuna prova di NDI di rete reale, Raspberry, Chromecast, QLab, cluster HA o
commutazione HDMI. TAKE resta logico. La release rimane alpha.

## Evidenze e ripetizione

Log sanitizzato, riepilogo e risultati JavaScript in `test-results/`.
Comandi nel README e istruzioni per controller in CONTROLLERS.md. Per evitare
test saltati servono le dipendenze controller, FFmpeg/ffprobe e un compilatore C.
Non distribuire la cartella dati, token o ambienti virtuali su GitHub.
