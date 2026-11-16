# Carisma Display Control v0.4 - Ricevitore NDI e player browser

## Che cosa e stato implementato

Il **server** riceve una sorgente NDI usando il runtime ufficiale, acquisisce video
ed audio tramite la API C/frame-sync e li passa a FFmpeg. FFmpeg produce H.264 +
AAC in piccoli segmenti MP4. Ogni player browser li legge dal server locale.

```
Sorgente NDI in LAN
       |
       v
Server Carisma: runtime NDI -> frame-sync -> FFmpeg H.264 / AAC
       |
       +---- player browser 1
       +---- player browser 2
       +---- altri player, entro le prestazioni misurate
```

Una sorgente e un profilo uguali usano **un solo ricevitore/encoder**, anche con
piu player. Profili diversi generano conversioni distinte. Il limite iniziale e
2 sorgenti/profili simultanei, modificabile con `--ndi-max-streams` da 1 a 8:
non e una certificazione della capacita del NEXCOM.

Il browser **non decodifica NDI nativamente**. Questa versione usa fMP4/H.264/AAC,
non WebRTC. Il buffering aggiunge ritardo: non usarla come monitor di palco a
latenza minima, per labiale garantito o per videowall sincronizzati al fotogramma.

**Stato di collaudo:** codice ricevitore implementato; pipeline e player provati
con generatore e ABI di test. La ricezione da un vero trasmettitore NDI, il
runtime ufficiale e il tuo NEXCOM NON sono stati collaudati in questo ambiente.
Vedi `QA_REPORT_v0.4.md` per distinguere precisamente le verifiche svolte.

## 1. Aggiornamento dalla v0.3

1. Conserva una copia della vecchia cartella.
2. Estrai la v0.4 in una cartella nuova.
3. A server fermo, copia la vecchia cartella `data/` nella nuova, per conservare
   SQLite, file caricati e chiave di accesso. Non sovrascrivere un server in uso.
4. Avvia il server dalla nuova cartella. Il formato dei progetti resta compatibile.

Le modifiche della demo aperta come file HTML sono nel browser, non in `data/`:
esporta il JSON dalla vecchia demo e importalo nella nuova console. Le immagini
e i video vanno trasferiti separatamente. `demo_compatta.html` e `index.html`
ora contengono la stessa console, evitando due implementazioni NDI divergenti.

## 2. Prima prova su Windows

Occorrono **Python 3.9+ a 64 bit**, **FFmpeg con libx264 e AAC** e, per NDI reale,
il **runtime/SDK NDI ufficiale a 64 bit**. Non occorrono pacchetti Python da pip.
Il solo generatore di prova richiede Python e FFmpeg, non NDI.

### Verifica e riparazione automatica (patch 0.4.1)

Esegui `Verifica_NDI_Windows.bat`: rileva le componenti presenti e installa quelle
mancanti. Nel caso Python e NDI siano gia funzionanti, scarica e predispone solo
FFmpeg, con checksum verificato e prova H.264/AAC. Usa la cartella del progetto,
non modifica PATH, firewall, `data/` o `Config_Locale.bat`.

La modalita senza installazioni e `Solo_Verifica_NDI_Windows.bat`.
Per dettagli, limiti e installazione su PC senza Python/NDI, leggi
`LEGGIMI_SETUP_WINDOWS_v0.4.1.md`. NDI eventualmente mancante usa l'installer
ufficiale con licenza visibile. La prima installazione richiede Internet o
pacchetti gia predisposti nella cache.

### FFmpeg

Installa una build appropriata tramite il tuo sistema oppure scaricala dai
riferimenti del progetto ufficiale: <https://ffmpeg.org/download.html>.
Puoi mettere `ffmpeg.exe` nella cartella `bin/`, renderlo disponibile nel PATH,
oppure indicarne il percorso tramite `CARISMA_FFMPEG`.

Non serve una build speciale FFmpeg con `libndi`: e il nostro modulo Python a
ricevere NDI. Non abbiamo incluso binari FFmpeg nell'archivio.

### Runtime NDI

Usa il runtime/SDK ufficiale: <https://ndi.video/for-developers/ndi-sdk/>.
Leggi e accetta personalmente la licenza prevista dal fornitore. Il pacchetto
Carisma non contiene DLL NDI, non aggira licenze e non usa decoder a pagamento.

Se il runtime non viene trovato automaticamente, rinomina
`Config_Locale.example.bat` in `Config_Locale.bat` e imposta i percorsi reali:

```bat
@echo off
set "CARISMA_NDI_LIBRARY=C:\percorso-reale\Processing.NDI.Lib.x64.dll"
set "CARISMA_FFMPEG=C:\percorso-reale\ffmpeg.exe"
```

Non usare i percorsi di esempio senza sostituirli. Conserva le eventuali
librerie accessorie del runtime nella loro installazione originale.

### Avvio e test

1. Esegui `Avvia_Windows.bat` e lascia aperta la finestra del server.
2. Apri **Ingressi NDI** nella console.
3. Verifica che FFmpeg sia disponibile. Premi **Apri test locale / NON NDI**.
   Deve comparire un video in movimento. L'audio parte disattivato.
4. Il test NON prova il protocollo NDI. Serve a verificare conversione e player.
5. Avvia la tua sorgente NDI in rete. Premi **Cerca sorgenti**; ripeti dopo qualche
   secondo se necessario.
6. Sulla sorgente trovata premi **Prova video**. Poi **Crea contenuto**.
7. In **Schermi**, aggiungi o seleziona un player, assegna la sorgente e premi
   **Apri player**. Il contenuto si apre in una finestra browser separata.
8. Premi **Attiva audio** nel player solo dove serve.

Puoi inserire il nome esatto della sorgente anche da **Contenuti -> Sorgente
live**. Esempio del formato: `PC-REGIA (Programma)`, non un URL `ndi://`.
Il nome deve corrispondere davvero a quello annunciato dal trasmettitore.

La sorgente deve essere un effettivo output NDI: non si presume che ogni
programma, incluso HeavyM, possa trasmettere NDI con qualunque configurazione.

## 3. Installazione sul mini PC Debian

Prepara questi componenti una volta, con accesso ai repository oppure usando un
repository/pacchetto offline gia predisposto per l'architettura corretta:

```sh
sudo apt update
sudo apt install python3 ffmpeg avahi-daemon libavahi-client3 libavahi-common3
sudo systemctl enable --now avahi-daemon
```

Scarica/seleziona il runtime Linux ufficiale per l'architettura effettiva, leggi
la licenza e installalo seguendo il fornitore. Poi, dalla cartella del progetto:

```sh
export CARISMA_NDI_LIBRARY=/percorso-reale/libndi.so.6
python3 diagnose_ndi.py
python3 server.py --host 0.0.0.0 --port 8787
```

Il nome reale del file puo variare: non rinominarlo sulla base dell'esempio.
Il percorso puo anche essere passato con `--ndi-library`; FFmpeg con `--ffmpeg`.

Apri `http://IP-DEL-NEXCOM:8787` dal PC di controllo e inserisci la chiave che il
server stampa e conserva in `data/access.key`. Questa chiave abilita anche
controlli e lettura dei contenuti: distribuiscila solo a postazioni fidate.

Questa guida non installa automaticamente un servizio di avvio 24/7. Il primo
collaudo va fatto in primo piano; dopo la misura di carico e stabilita si puo
preparare il servizio systemd con utente dedicato e percorsi definitivi.

## 4. Funzionamento senza Internet e perdita del segnale

L'app non usa CDN, autenticazione cloud, STUN/TURN pubblici o API esterne.
Dopo aver predisposto Python, FFmpeg e runtime, la normale esecuzione e locale.
Il collegamento al sito NDI nella console e informativo, non viene caricato
automaticamente. Le condizioni del runtime/licenza restano applicabili.

- **Internet assente, LAN presente:** il gateway e i player possono funzionare.
- **LAN/server assenti:** niente live. Il player aperto passa al fallback locale.
- **Sorgente NDI bloccata o sparita:** il gateway controlla i nuovi frame, non solo
  la connessione dichiarata; il player passa al fallback e riprova.
- **Ritorno del segnale:** il player ritenta automaticamente, preparando il buffer.
- **Palinsesto locale:** continua a essere valutato sul player.

Scegli per ogni schermo un fallback: per esempio l'orologio animato. Aspetta che
la cache sia pronta prima di isolare il player.

Il riavvio del browser completamente senza rete via normale HTTP su un IP LAN
non e garantito: il service worker richiede localhost o HTTPS. L'app Android
nativa per Chromecast resta da sviluppare e verificare. Questa modifica non
sblocca il bootloader G454V e non installa software sul dispositivo.

## 5. Profili, memoria, audio e limiti

| Profilo | Video in uscita | Audio |
|---|---|---|
| Leggero, predefinito | 640x360, 15 fps, obiettivo 800 kbit/s | AAC stereo 48 kHz, 128 kbit/s |
| Standard | 1280x720, 25 fps, obiettivo 2,2 Mbit/s | AAC stereo 48 kHz, 128 kbit/s |

I bitrate sono obiettivi dell'encoder, non limiti rigidi o misure sul tuo hardware.
La risoluzione d'ingresso viene adattata mantenendo le proporzioni; audio
ricampionato dal frame-sync. Va verificata sul posto anche la sincronizzazione
percepita audio/video. In assenza di audio il frame-sync puo produrre silenzio.

Il ritardo comprende ricezione NDI, conversione, segmentazione e buffer del
browser: il buffer visibile non e una misura della latenza end-to-end.
Non e stata implementata accelerazione hardware dell'encoder. Il NEXCOM va
misurato prima di passare a 720p o piu ingressi.

La cache dei segmenti e una finestra scorrevole breve in `data/live/`, non una
registrazione. I segmenti vecchi vengono rimossi; il gateway senza lettori viene
arrestato dopo circa 60 secondi. La cartella non va inclusa nei backup dei media.
Il log `encoder.log` serve alla diagnosi della singola esecuzione; non e ancora
un sistema di log rotation industriale.

La libreria NDI gestisce la decodifica d'ingresso. La presenza di una sorgente
**HX/HX3/H.265 non ne garantisce la decodifica**: dipende dal runtime, dai codec e
dalla piattaforma, specialmente su Linux. Prova dapprima una sorgente NDI High
Bandwidth nota; verifica separatamente il tuo encoder H.265.

## 6. Rete e sicurezza

Per il collaudo usa la stessa subnet/VLAN e preferibilmente Ethernet. Se il
finder non vede sorgenti, controlla mDNS/Avahi e firewall. Non disattivare tutte
le protezioni del PC. Le porte NDI dipendono dalla configurazione ufficiale.
Per cercare su host specifici puoi usare:

```sh
python3 server.py --host 0.0.0.0 --ndi-extra-ips 192.168.1.10,192.168.1.11
```

Il traffico gateway-player usa HTTP sulla porta configurata, predefinita 8787.
Le socket del trasferimento grezzo verso FFmpeg ascoltano solo su loopback.
Le API NDI, incluse quelle dei segmenti, richiedono `X-Control-Token`.
Non esporre questa versione su Internet: HTTP e chiave condivisa non sostituiscono
TLS, utenti separati, autorizzazioni per player e un controllo di sicurezza completo.

## 7. Test ripetibili

```sh
python3 -m unittest discover -s tests -v
```

I test del controller non richiedono Internet. I test di conversione richiedono
FFmpeg; quello ABI richiede GCC e compila una libreria fittizia temporanea.
`tests/fake_ndi.c` **non e un ricevitore NDI**: nessun suo binario viene incluso
nel pacchetto e non deve essere configurato come runtime nell'impianto.

## Licenze e attribuzione

NDI(R) is a registered trademark of Vizrt NDI AB.
<https://ndi.video/>. Il runtime e proprietario e resta soggetto alla sua licenza.
Non e corretto descrivere l'intera catena come completamente open source.
Il progetto non implementa canoni o acquisti di app di terzi; eventuali usi
commerciali/distribuzioni vanno verificati rispetto ai termini SDK applicabili.
FFmpeg e i codec mantengono le proprie licenze. Nessun binario di terzi incluso.
