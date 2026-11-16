> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Carisma v0.4 - Rapporto di verifica

## Esito sintetico

**15 test automatici Python superati.** Il client browser riproduce segmenti
H.264/AAC generati dal vero FFmpeg di questo ambiente. Non e stato disponibile
un runtime NDI ufficiale o un trasmettitore fisico: non si dichiara collaudo di
ricezione NDI reale.

## Test Python effettuati

- API protette, chiave errata, persistenza SQLite e revisione concorrente.
- Importazione file, hash, download autenticato e payload non validi.
- API NDI/segmenti protette, profili e JSON rifiutati correttamente.
- Struct ABI a 64 bit: video v2 72 byte, audio v2 56 byte.
- Copia righe con stride e conversione audio planare/interleaved.
- Assenza runtime dichiarata come errore, non come ricezione riuscita.
- Generatore NON NDI -> FFmpeg -> init MP4 e segmenti reali H.264/AAC.
- Condivisione encoder, limite ingressi e rifiuto path traversal.
- Segnale vecchio marcato non sano.
- Libreria C fittizia compilata localmente: discovery, frame-sync, conteggi,
  video con padding, audio, passaggio raw a FFmpeg e decodifica dei segmenti.
  Quest'ultimo test esercita il nostro binding, NON il protocollo o SDK ufficiale.

Comando: `python3 -m unittest discover -s tests -v`.
Durata dell'ultima esecuzione in questo ambiente: circa 8 secondi.

## Test browser effettuati

Chromium headless installato nell'ambiente:

- Sintassi JavaScript valida e nessun page error nelle prove concluse.
- Player di anteprima: 640x360, currentTime crescente, readyState 4, nessun errore
  media; buffer rilevato circa 1,8 secondi in una prova, NON latenza end-to-end.
- Aggiunta player tramite interfaccia, assegnazione test video e apertura logica
  in una seconda pagina browser.
- Pulsante audio: video passa da muted a unmuted. Non effettuata prova d'ascolto.
- Distacco simulato player -> fallback all'orologio locale.
- Ricollegamento -> riproduzione del flusso ripristinata.
- Arresto reale encoder tramite API -> fallback; ripartenza automatica -> video.
- Due pagine player indipendenti riproducono lo stesso flusso con un solo encoder.
- Console mobile a 390 px senza overflow orizzontale.

### Limite dell'ambiente browser

Il Chromium del container blocca la navigazione HTTP e file tramite policy.
Non e stata modificata o aggirata la policy. La pagina e stata caricata come
fixture con `set_content`: nel test il trasporto fetch era sostituito da un
ponte verso le API locali reali, e IndexedDB/localStorage da storage di test.
FFmpeg e i byte MP4 erano reali; non e una verifica di accesso HTTP diretto dalla
LAN, Service Worker, storage persistente o permessi popup del PC dell'utente.
I test HTTP/API sono stati eseguiti separatamente con il client Python.

Una prima sessione di regressione browser ha raggiunto il limite di durata del
runner dopo le verifiche di recupero: la prova a due player e il layout mobile
sono stati completati in una sessione separata. Non sono state ignorate
asserzioni fallite per dichiarare un esito positivo.

## Ancora da collaudare sul posto

1. Runtime NDI ufficiale e sorgente reale: HB, poi specifico encoder HX/H.265.
2. Audio percepito, labiale, compatibilita browser e riavvio prolungato.
3. CPU/temperature del NEXCOM, resa a 360p/720p, numero massimo di ingressi/player.
4. LAN UniFi, firewall, mDNS/Avahi, interruzione fisica della rete e recupero.
5. Windows nativo, popup, media autoplay, codec e storage effettivi dell'utente.
6. Riavvio offline via HTTPS/localhost e futura applicazione Chromecast.
7. Uso continuativo 24/7, log rotation e revisione sicurezza prima di produzione.

Non e stata installata una ROM, modificato il bootloader o raggiunto un Chromecast.
