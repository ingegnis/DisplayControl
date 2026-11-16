> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Carisma v0.5-alpha — rapporto di verifica

## Esito

- **65 test Python superati** nell'ultima esecuzione (23,531 secondi). Inclusi i 39 test preesistenti, 17 nuovi test delle API dei player, 7 controlli delle utility di build Android e 2 test dell'avvio LAN.
- **27 controlli della classe Java NetworkPolicy superati**, compilata con JDK 21 in compatibilita Java 8. Questi sono controlli Java desktop, non test Android.
- **11 scenari/controlli browser completati** usando fixture esplicite; API HTTP e FFmpeg reali, navigazione e storage persistente non collaudati.
- Sintassi Python, XML del manifest e 7 blocchi/script JavaScript verificata.
- **APK Android NON compilato e NON installato.** SDK Android assente; il tentativo di build senza SDK termina correttamente con errore e non produce un APK. Il download SDK nell'ambiente non era disponibile. Non e stato raggiunto un Chromecast.

Il pacchetto non contiene file APK, non contiene binari SDK/NDI/FFmpeg e non contiene chiavi private di firma. `build_android.py` e `Windows_Android.ps1` sono procedure da eseguire sul PC, non risultati di una build nativa verificata.

## Ambiente

Linux x86_64, Python 3.13.5, OpenJDK 21.0.12.1, FFmpeg 7.1.5, Chromium 144.0.7559.96. L'ambiente non e il Windows 10/11 del cliente, il NEXCOM o il Chromecast G454V. Dettagli in `qa/environment.json`.

## API e server: prove reali

I test avviano un processo Python, un database SQLite temporaneo e richieste HTTP vere su loopback. Sono stati verificati:

- Necessita della chiave amministratore per generare/revocare codici e vedere i dispositivi.
- Codici monouso, scadenza, invalidazione del codice precedente e limite di tentativi.
- Due richieste concorrenti sullo stesso codice: una sola riesce.
- Credenziali player memorizzate come hash; token amministratore e player non intercambiabili.
- Un player vede solo il suo schermo, playlist, palinsesti e contenuti necessari.
- Impossibilita di modificare la regia, inviare heartbeat per altri schermi o fermare encoder.
- Revoca e sostituzione token; schermo eliminato non piu accessibile.
- Heartbeat visibile e campi numerici/stringa limitati e validati.
- Download con hash corretto di un file solo dopo assegnazione.
- Divieto di avviare sorgenti NDI/test non assegnate.
- Generazione reale con FFmpeg di init MP4 e segmenti fMP4, lettura dal player autorizzato e rifiuto dopo riassegnazione.
- Avvio LAN con `--host 0.0.0.0` solo quando richiesto; avvio normale mantiene il default locale.

Log integrale: `qa/python-tests.log`.

## Java e preparazione SDK

`NetworkPolicy` rifiuta server pubblici, URL con credenziali/percorso/query, IPv4 malformati, porte non valide e API non autorizzate. Accetta gli indirizzi IPv4 privati previsti e i percorsi init MP4 / segmenti m4s del gateway.

Le utility Python rifiutano ZIP con path traversal, non riscaricano cache con hash verificato e rifiutano checksum errati. Il manifest dichiara un launcher TV senza touchscreen richiesto e senza permessi privilegiati. Gli asset HTML/JS inclusi nell'app corrispondono a quelli del player distribuito.

**Non sono verificati:** esecuzione di sdkmanager, compilazione completa di MainActivity contro android.jar, D8/aapt2, firma APK, bootstrap PowerShell e ADB su Windows. Il log `qa/android-build-unavailable.log` riporta la build interrotta per SDK assente. Nessun risultato positivo di compilazione Android e dedotto dai test Java desktop.

## Browser: 11 scenari/controlli con limiti dichiarati

1. Console: elenco schermi, generazione codice tramite API reale, elenco dispositivo associato.
2. Layout mobile a 390 px senza overflow orizzontale.
3. Shell player: orologio e stato limitato allo schermo assegnato.
4. Interruzione del trasporto: conservazione del vecchio contenuto dopo un nuovo comando del server.
5. Ripristino del trasporto: applicazione del nuovo contenuto.
6. Riavvio logico della shell con snapshot iniettato e API assente: appare l'orologio.
7. Riproduzione MediaSource di segmenti H.264/AAC prodotti da FFmpeg reale; currentTime avanza.
8. Due player in pagine separate con un solo encoder FFmpeg effettivamente attivo.
9. Perdita del collegamento live: fallback all'orologio locale.
10. Ripristino collegamento: riproduzione video ripresa.
11. Nessun errore JavaScript non gestito nelle fixture completate.

### Limite tecnico importante

La policy del browser dell'ambiente blocca la navigazione diretta verso HTTP locale (`ERR_BLOCKED_BY_ADMINISTRATOR`). Non e stata disabilitata o aggirata. Le pagine sono state caricate con `set_content`; una funzione di trasporto di test passa le richieste a vere API locali. IndexedDB e localStorage sono sostituiti da mappe in memoria; i parametri URL della shell sono impostati dalla fixture.

Quindi il punto 6 **non certifica la persistenza di IndexedDB o il riavvio fisico offline**. Analogamente questi test non certificano popup, accessibilita LAN, permessi, WebView Android o rendering hardware del Chromecast. Il byte stream FFmpeg e reale; il trasporto browser e adattato per il test. Le schermate in `qa/` rappresentano queste fixture, non un Chromecast installato.

Comando del runner: `python tests/browser_fixture_check.py` (Playwright e Chromium richiesti solo per i test). L'eseguibile Chromium si puo specificare con `CARISMA_QA_CHROMIUM`.

## Cosa rimane da collaudare sul posto

- Build APK e installazione sul primo G454V.
- Navigazione e pairing dalla LAN Windows/UniFi, regole firewall e subnet.
- Telecomando, audio percepito, compatibilita WebView/codec, consumo RAM e temperatura.
- Sincronizzazione iniziale di immagini/video, riapertura app offline con cache realmente persistente.
- Disconnessione fisica LAN, ripristino, spegnimento elettrico e deriva dell'orologio.
- Ricezione da sorgente NDI reale e dallo specifico encoder HX/H.265.
- Funzionamento prolungato e carico di piu ingressi/player sul NEXCOM.

**Non implementato:** autostart dell'app dopo accensione del Chromecast, sostituzione del launcher, watchdog di sistema, decodifica NDI diretta sul Chromecast, videowall sincronizzato al fotogramma, gestione multiutente con TLS di produzione. Il firmware Google resta invariato.

## Ripetibilita

```sh
python -m unittest discover -s tests -v
javac --release 8 -d java-test android-player/src/it/carisma/player/NetworkPolicy.java android-player/PolicyTest.java
java -cp java-test PolicyTest
```

Per provare la build effettiva su una macchina con JDK/SDK e licenze accettate:

```sh
python build_android.py --sdk /percorso/reale/sdk
```

Il successo dell'APK richiede tutti i passaggi di compilazione e verifica della firma. Il successo di installazione richiede una risposta valida del dispositivo e il controllo dello schermo; nessuno dei due e stato anticipato nel rapporto.
