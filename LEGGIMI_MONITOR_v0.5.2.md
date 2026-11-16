# Carisma v0.5.2-alpha - Monitor schermi e latenza ridotta

## Aggiornamento unico dalla v0.5-alpha o v0.5.1

Questa patch include SIA il nuovo monitor SIA la correzione della latenza.
Non serve applicare separatamente la patch v0.5.1.

1. Ferma il server e conserva una copia della cartella del progetto.
2. Estrai Carisma_Aggiornamento_Monitor_Latenza_v0.5.2.zip in una cartella temporanea.
3. Copia tutto il contenuto nella cartella di server.py, sostituendo i file e
   unendo le sottocartelle. Non eseguire il programma dentro lo ZIP.
4. Riavvia Avvia_Server_LAN_Windows.bat.
5. Ricarica la regia E OGNI PC PLAYER con Ctrl+F5. Non eliminare dati del browser
   o abbinamenti: basta ricaricare il codice. I player rimasti aperti con il vecchio
   codice continuano a funzionare ma non producono miniature.
6. In regia premi Monitor schermi. In alternativa apri:

   http://IP-DEL-SERVER:8787/monitor.html

Usa il vero indirizzo del server, non quello del client. Se richiesto, inserisci
la chiave amministratore data/access.key, non il codice di abbinamento.

La patch NON contiene data/, bin/, .setup/, Config_Locale.bat, credenziali,
DLL NDI o file multimediali utente. Non cancella ne migra schermi, programmi o
abbinamenti. Non installa pacchetti nuovi e non modifica il firewall.
Per aggiornare una versione precedente alla v0.5 usa invece il progetto completo
seguendo prima le istruzioni di collegamento dei player fisici.

## Pagina Monitor schermi

- Tutti gli schermi configurati, compresi quelli mai collegati.
- Intervallo selezionabile 1, 2 o 5 secondi (predefinito 2).
- Filtri per gruppo e stato; griglia da 2, 3 o 4 colonne e schermo intero.
- Nome, gruppo, ultimo contenuto dichiarato, eta dell'anteprima, stato del player.
- Evidenza di fallback, test offline e player non raggiungibile.
- Pausa/ripresa senza interrompere la riproduzione sugli schermi.
- Quando disponibile, coda del player in secondi: NON latenza totale NDI.

Un player senza contatti per circa 13 secondi viene segnato non raggiungibile;
la sua ultima anteprima resta ferma con un'etichetta e il tempo trascorso.
Anche se il server non risponde, le vecchie immagini NON vengono presentate
come aggiornamenti in diretta. Un player mai visto non mostra un'anteprima
inventata dal contenuto programmato in regia.

Gli intervalli sono obiettivi, non un sincronismo garantito: elaborazione,
richieste HTTP e limitazioni del browser possono renderli piu lunghi. All'apertura
la prima anteprima richiede il prossimo contatto del player (normalmente ogni
2,5 s), una cattura e il successivo aggiornamento del monitor.

## Che cosa rappresentano le immagini

Video locali e live: JPEG ottenuto dal fotogramma del video decodificato nel
player con Canvas drawImage. Immagini: copia ridotta dell'immagine caricata.
Sono etichettati FOTOGRAMMA DAL PLAYER. Non viene aperto un decoder NDI aggiuntivo
per il monitor: non vengono avviati altri encoder FFmpeg.

Orologi e schermate grafiche: miniatura ricostruita sul player dai testi,
dall'ora e dai colori effettivamente presenti nella sua pagina. Sono etichettati
GRAFICA RICOSTRUITA. Non e una cattura pixel-per-pixel del DOM e non riproduce
necessariamente tutti gli effetti CSS. Schermo nero: miniatura nera dichiarata.

Tutte le anteprime provengono dal software del player; NON sono fotografie del
televisore, screenshot del desktop o una verifica del cavo HDMI/TV acceso.
Per stream HTTP esterni la protezione cross-origin del browser puo impedire
la cattura: in tal caso viene segnalata ANTEPRIMA NON DISPONIBILE, senza bloccare
il player. La pipeline Carisma usa media locali/Blob e viene provata nei test.

## Risparmio di banda e conservazione

Miniature JPEG fino a 480x270, compressione 0,58, limite 64 KiB per JPEG.
Vengono inviate solo quando almeno un monitor amministratore le richiede.
Chiudendo, nascondendo o mettendo in pausa l'ultimo monitor la richiesta termina;
se la chiusura non puo inviare un messaggio, la concessione scade entro 12-15 s.
Il player riceve la nuova policy al contatto successivo o alla risposta di upload.
Con piu monitor vale l'intervallo piu breve ancora richiesto.

Il server conserva soltanto l'ultima miniatura per player in RAM, non un archivio
video o una cronologia. Le immagini spariscono al riavvio del server; revoca o
nuovo abbinamento rimuovono la precedente anteprima. Il monitor riscarica il JPEG
solo quando il contenuto JPEG cambia. Le immagini delle schede nascoste dai
filtri non sono scaricate, ma i player continuano a inviarle mentre il monitor
richiede la raccolta generale.

Il contatore di traffico del monitor conta il corpo delle risposte ricevute
negli ultimi 15 s (JPEG e JSON), NON tutto il traffico di rete, header HTTP,
stream NDI o upload dei player. Gli upload JPEG sono incapsulati in base64
(con relativo overhead), le risposte immagini sono binarie.

Esempio di calcolo, non misura del tuo impianto: 20 immagini da 10 kB rinnovate
tutte ogni 5 s equivalgono a circa 40 kB/s verso un monitor, esclusi metadati.
La quantita effettiva varia con il contenuto. Nei quattro esempi del test locale
le singole miniature misuravano circa 7,3-8,4 kB.

## Correzione della latenza inclusa

La v0.5 teneva il player 2 s dietro l'ultimo video disponibile e usava segmenti
nominali da 1 s. La modalita Reattiva ora usa obiettivo buffer 0,75 s e segmenti
obiettivo 0,5 s (0,533 s a 15 fps, 0,520 s a 25 fps), keyframe allineati,
polling segmenti da 100 ms e recupero dell'arretrato. Nel player c'e Torna alla
diretta. Non elimina il ritardo a monte del gateway.

Dopo il riavvio, Ingressi NDI deve indicare Reattiva / LAN. Se avevi impostato
CARISMA_LIVE_MODE=stable in Config_Locale.bat, cambia solo tale valore in
responsive. Non cancellare le altre impostazioni.

Per tornare alla modalita piu conservativa, aggiungi o modifica:

```bat
set "CARISMA_LIVE_MODE=stable"
```

Poi riavvia server e ricarica i player. Il maggiore margine di buffer puo
aiutare su reti irregolari ma aggiunge ritardo. La documentazione dettagliata
LEGGIMI_LATENZA_v0.5.1.md resta inclusa; la procedura di installazione da seguire
per questa consegna e quella v0.5.2 riportata sopra.

Le misure del precedente confronto locale davano coda media 1,807 s in Stabile
contro 0,632 s in Reattiva. Sono prove FFmpeg/Chromium, NON la latenza reale del
tuo NDI. Per misurarla mostra un cronometro sulla sorgente realmente trasmessa e
riprendi insieme sorgente e monitor client: confronta i due valori nello stesso
fotogramma. Confronta inoltre il Test locale / NON NDI e la sorgente reale.

## Sicurezza, offline e limiti

La pagina monitor richiede credenziali amministratore. Ogni player puo inviare
solo la propria miniatura; non puo leggere il monitor o le immagini degli altri.
Non esporre questa versione HTTP su Internet o reti ospiti. Le immagini possono
contenere contenuti riservati: tratta la console come una postazione di regia.

L'assenza di Internet non impedisce il monitoraggio locale. Serve pero la LAN:
non si puo osservare in diretta uno schermo isolato dalla rete. Il suo ultimo
programma locale puo continuare anche quando il monitor lo vede assente.
Il riavvio del browser HTTP completamente offline non diventa garantito con
questa patch: rimane il limite documentato della v0.5.

Sorgenti Android aggiornati e versionati, ma nessun APK o test Chromecast nuovo.
Un'app gia installata incorpora il vecchio codice: serve ricompilarla e
reinstallarla; Ctrl+F5 riguarda solo i player browser su PC.
Il nome storico del file APK generato dallo script resta v0.5-alpha; il manifest
dei sorgenti e 0.5.2-alpha, versionCode 52. Non e stato compilato qui.

## Riferimenti tecnici

https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob
https://developer.mozilla.org/en-US/docs/Web/API/Media_Capture_and_Streams_API/Taking_still_photos
https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
https://ffmpeg.org/ffmpeg-formats.html

Leggi QA_MONITOR_v0.5.2.md per prove, risultati e limiti dell'ambiente.
