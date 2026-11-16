# Test DisplayControl 0.9.0-alpha

Verifica completata il 16 novembre 2026 su Windows x64, Python 3.14.7 e Node.js.

## Esito

- **127 test Python completati: 0 errori, 0 fallimenti, 0 saltati.**
- Tre suite JavaScript superate: policy diretta, palette/contrasto/logo, timeline Prompt.
- Sintassi di 20 script JavaScript verificata; compilazione sintattica dei moduli Python completata.

| Area | Prova | Esito e portata |
|---|---|---|
| Prompt | Copioni/cue, tre opzioni grafiche, API e pairing | Superata sul software |
| Sincronismo | 20 JOG+, anteprima ridotta contro player a schermo intero | Identici margini, font, coordinate delle righe e posizione a pausa |
| Ridimensionamento | Finestre 800×600 e 1920×1080 | Nessuna reimpaginazione; coordinate virtuali identiche |
| Guasto server | Processo del server di prova arrestato mantenendo aperti regia e player | Scorrimento locale proseguito; player ha indicato offline |
| Riavvio | Stessa cartella dati, browser rimasti aperti | Riconnessione automatica; scarto dall'avanzamento atteso 0.239 pixel virtuali nella misura raccolta |
| Controller | Eventi HID e LCD simulati, code scadute, STOP prioritario, USB/LCD persi | Superata con dispositivo fittizio; nessuna prova di USB reale |
| Pairing | Codici scaduti/monouso, revoca, token limitati, richieste concorrenti duplicate | Superata via HTTP reale su loopback e SQLite |
| Fallback | Core rifiutato, timeout ambiguo, cambio endpoint e UDP OSC vero su loopback | Nessun aggiramento della revoca e nessuna ripetizione relativa dopo esito incerto |
| FFmpeg | Test pattern, frammenti H.264/AAC, profili 360p/720p, keyframe e decodifica | Superata con FFmpeg/ffprobe reali |
| Interfaccia NDI C | DLL di test compilata con Visual C, ricezione simulata, perdita/ripresa segnale e decodifica FFmpeg | Superata; la DLL non implementa il protocollo NDI |
| Monitor | Miniature, domanda di anteprima, permessi, revoca e dati assegnati | Superata tramite API e fixture; nessun display fisico coinvolto |
| Player signage | Abbinamento, cache/configurazione assegnata, accesso ai segmenti FFmpeg | Superata via API; non certifica Raspberry/Chromecast |
| Nome/logo/tema | Upload PNG sintetico nel browser, proposta palette, applicazione, salvataggio e ricaricamento | Superata in modalità demo; persistenza server/esportazione verificata anche via API |
| Android | Verifiche dei sorgenti, policy e coerenza degli asset inclusi | Superata; APK non compilato né eseguito qui |

## Correzioni rilevanti

- Chiuse esplicitamente le connessioni SQLite per evitare file bloccati su Windows.
- Motore condiviso Prompt con pagina virtuale 1280×720 e timeline monotona; risposte più vecchie non riportano indietro lo scorrimento.
- Cache del player limitata a una scrittura al secondo anziché riscrivere l'intero copione a ogni polling.
- Controller: configurazione atomica, token distinti per endpoint, code limitate e senza recupero tardivo; scritture HID incomplete rilevate; errori LCD riportano il dispositivo in riconnessione.
- Richieste controller con identificativo deduplicate in transazione insieme allo stato, conservate per 24 ore sul singolo Core. Non sono una deduplicazione fra database indipendenti.
- Nome, logo ridimensionato e tema restano nel progetto; nessun logo viene applicato al copione.

## Limiti e collaudo necessario

Nessun AKP03E, Raspberry, Chromecast, monitor HDMI, sorgente NDI di rete o QLab fisico è stato collaudato. Restano da verificare sul posto enumerazione USB, orientamento LCD, numerazione encoder, hot unplug, rendering con font installati su sistemi diversi, latenza della LAN e prestazioni a pieno carico.

Il cambio Core HTTP non replica lo spettacolo e non implementa quorum, VIP, witness o fencing. Preparare e abbinare ogni endpoint separatamente; TAKE rimane logico. OSC UDP non offre autenticazione o conferma di consegna e deve restare sulla rete di controllo fidata. Lo STOP è prioritario nella coda ma non è un comando hardware di emergenza: eventuali attese di rete ne influenzano la latenza.

Un'interruzione improvvisa del processo Windows può lasciare un encoder esterno da chiudere; le prove arrestano gli encoder prima della pulizia. Non è verificata qui la tenuta dopo sospensione completa del sistema operativo. La continuità di un player già aperto non certifica l'avvio a freddo offline su indirizzi LAN HTTP.

Ricaricare regia e player dopo la patch, senza mescolare versioni 0.8 e 0.9. Le unità dei comandi preesistenti ora rappresentano pagine virtuali: ricontrollare le velocità operative e i cue prima di uno spettacolo. Il copione viene impaginato con font di sistema; per confronti fra OS diversi installare gli stessi font.

## Riproducibilità

Comandi nel README; log e misure sanitizzati in `test-results/`. I rapporti `QA*` inclusi sono documentazione storica e non attestano questa release. Il test ABI usa soltanto `tests/fake_ndi.c`; i binari NDI proprietari non sono inclusi.

Riferimenti per le correzioni: [gestione connessioni SQLite in Python](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager), [muxer HLS FFmpeg](https://ffmpeg.org/ffmpeg-formats.html#hls-2). Gli esiti sopra provengono dall'esecuzione locale dei test, non dai riferimenti.
