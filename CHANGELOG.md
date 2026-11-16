# 0.9.0-alpha

- Sincronismo Prompt indipendente dalla larghezza della finestra; timeline condivisa e recupero dopo riavvio.
- Nome dell'organizzazione, logo discreto e proposta di tema dai colori dell'immagine.
- Resilienza controller HID/HTTP/OSC, token per Core e deduplicazione sul singolo database.
- Chiusura deterministica SQLite su Windows e regressione FFmpeg/ABI completata.
- Preparazione del repository pubblico con esclusione dei dati locali. Dettagli in TEST_REPORT.md.

# v0.7-alpha — Carisma Prompt

- Gobbo elettronico con copione TXT/DOCX e cue.
- Scroll locale sui player e cache offline.
- Tre preset per font, dimensione e colori.
- Controllo jog/shuttle da tastiera USB.
- Listener OSC UDP (porta 9000 di default) con allow-list IP opzionale.
- Player PRIMARY + BACKUP hot mirror con stato e delta di sincronismo.
- Pagina regia `/prompt.html` e player `/prompt_player.html`.

# v0.5.2-alpha

Monitor con miniature dai player, intervalli 1/2/5 s, richiesta on-demand, stato e fallback, accessi separati. Include correzione latenza v0.5.1. Vedi LEGGIMI_MONITOR_v0.5.2.md.

# v0.5.1-alpha - buffering ridotto

- Segmenti target 0.5 s (keyframe allineati), buffer target 0.75 s, polling 100 ms.
- Recupero arretrato dopo stall e pulsante Torna alla diretta.
- Modalita stable disponibile per confronto; --live-mode o CARISMA_LIVE_MODE.
- Coda player esplicitamente distinta dalla latenza totale.
- 75 test Python, 17 controlli JS, regressioni browser e misure in fixture.
- Nessuna modifica ai dati, pairing, runtime NDI o firewall.

# v0.5-alpha — player fisici

- Avvio LAN esplicito e pagina di abbinamento con codici monouso da 8 cifre.
- Credenziali per schermo: stato, contenuti, heartbeat e gateway limitati al player.
- Revoca e sostituzione abbinamenti, codici scaduti e rate limiting.
- Pagina player dedicata avviabile da shell offline.
- Sorgente Android TV Java/WebView, menu telecomando, builder SDK e installazione ADB guidata.
- Nessun APK incluso: build/Android/Chromecast ancora da verificare sul posto.

## 0.4.1 - Riparazione delle dipendenze Windows

- Verifica Windows con download/installazione selettiva delle dipendenze.
- FFmpeg locale, checksum, estrazione sicura, staging e backup precedente.
- Bootstrap Python x64 con hash e Authenticode; nessun aggiornamento forzato.
- Runtime NDI solo quando necessario, installer con licenza/UAC visibili.
- Test reale di conversione H.264/AAC, modalita sola diagnosi, log e percorsi salvati.
- Zero sorgenti NDI non equivale a installazione fallita.
- Nessuna modifica a dati, palinsesti, Config_Locale o firewall.

# v0.4 - Ricezione NDI sul server e player live

- Binding ctypes NDI ufficiale: discovery, ricezione video/audio, frame-sync.
- FFmpeg H.264/AAC, segmenti fMP4 e client MediaSource senza CDN.
- Pagina Ingressi NDI, sorgenti manuali/rilevate, profili e anteprima.
- Encoder condiviso per sorgente/profilo; arresto dopo inattivita.
- Fallback, tentativi di recupero, audio attivabile dal browser.
- Generatore locale esplicitamente NON NDI e diagnostica installazione.
- Runtime proprietario e FFmpeg non inclusi; ricezione reale da collaudare.
- 15 test Python superati; prove browser documentate con limiti dell'ambiente.
- La precedente demo compatta usa ora la stessa console completa.

---

# v0.3.0 - Player aggiungibili e finestre dedicate

- Demo compatta: creazione, modifica ed eliminazione dei player, gruppi e temi orologio.
- Una finestra browser nominata per player, con schermo intero e controlli nascondibili.
- Comunicazione locale tra finestre, memoria dell'ultimo programma e test offline.
- Configurazione persistita nel browser quando lo storage e disponibile.
- Fallback di comunicazione tramite messaggi, BroadcastChannel e storage locale.
- Console completa: creazione player piu visibile, selezione dopo creazione,
  gestione popup e proporzioni 16:9 della finestra player.
- Nessuna nuova dipendenza, nessuna integrazione Chromecast o NDI in questa release.

# 0.2.0

- Nuovo contenuto Orologio e data, completamente locale.
- Tre temi, cifre animate, data italiana, secondi e fuso configurabili.
- Supporto in libreria, schermi, palinsesti, playlist e fallback.
- Migrazione non distruttiva dei progetti 0.1; cache della shell aggiornata.
- Preferenza per movimento ridotto rispettata.

I limiti della versione 0.1 su player browser e gateway NDI restano invariati.

## 0.8.0-alpha — AJAZZ AKP03E
- Supporto diretto USB HID AJAZZ AKP03E (0300:3002), senza software vendor durante lo show.
- Sei LCD dinamici, tre encoder premibili e tre pulsanti laterali mappati a Carisma Prompt.
- Pairing/controller token dedicato e API con permessi minimi.
- `activeRole` e TAKE PRIMARY/BACKUP, anche via OSC.
- Fallback OSC opzionale a due Core quando HTTP non e raggiungibile.
- Installer/test/configuratore Windows e udev rule Linux.
