> Documentazione storica. Per la release corrente leggi README.md e TEST_REPORT.md.

# Aggiornamento v0.5.2-alpha

Per monitor e correzione latenza leggi **LEGGIMI_MONITOR_v0.5.2.md**. Il nuovo monitor e `/monitor.html`; richiede la versione server e player ricaricati.

# Aggiornamento v0.5.1-alpha: diretta piu reattiva

Leggi **LEGGIMI_LATENZA_v0.5.1.md** e **QA_LATENZA_v0.5.1.md**.

# Aggiornamento v0.5-alpha: player fisici

Leggi prima **LEGGIMI_PLAYER_FISICI_v0.5.md** e **QA_PLAYER_FISICI_v0.5.md**.
Sono disponibili abbinamento e player browser in LAN; il sorgente Android TV e il builder sono inclusi, ma **non un APK gia compilato/collaudato**. Gli avvii LAN sono espliciti; il normale avvio resta locale.

---

> **Aggiornamento Windows 0.4.1:** `Verifica_NDI_Windows.bat` ora installa le
> dipendenze mancanti e ripete il test. La sola diagnosi e
> `Solo_Verifica_NDI_Windows.bat`. Leggi `LEGGIMI_SETUP_WINDOWS_v0.4.1.md`.
> La console/gateway restano quelli della v0.4; questa e una patch del setup.

# Carisma Display Control v0.4

Console di digital signage locale, player browser separati, orologio animato,
playlist/palinsesti offline e nuovo gateway **NDI -> H.264/AAC -> browser**.

## Inizia qui

**Leggi `LEGGIMI_NDI.md` per installazione, test e limiti.**

Su Windows: `Verifica_NDI_Windows.bat`, poi `Avvia_Windows.bat`.
Su Linux: `python3 diagnose_ndi.py`, poi `python3 server.py`.

Aprire `index.html` senza server permette di esplorare l'interfaccia ma **non
riceve NDI**. Per riprodurre un live occorrono server, FFmpeg e runtime NDI
ufficiale; quest'ultimo non serve per il test video locale non-NDI.

`demo_compatta.html` contiene la stessa console della v0.4. Il pacchetto conserva
la compatibilita del progetto e della cartella dati della v0.3.

## Funzioni

- Player aggiungibili, gruppi, finestra separata e comandi dalla regia.
- Schermate, orologio con data, immagini/video locali, playlist e palinsesti.
- Cache prima dell'attivazione di un nuovo programma e fallback locale.
- Discovery NDI, ricevitore API C/frame-sync, audio stereo, encoder condiviso.
- Anteprima del gateway, test non-NDI, diagnostica, riconnessione automatica.
- Python standard library; nessuna dipendenza pip o JavaScript remota.

## Confine del collaudo

Sono inclusi test di controller, ABI fittizia e conversione. La decodifica con
runtime ufficiale, trasmettitore fisico, NEXCOM e Chromecast richiede collaudo sul
posto. L'app nativa Android/Chromecast e il bootloader NON sono modificati.
La distribuzione a segmenti aggiunge latenza e non sincronizza un videowall.
Vedi `QA_REPORT_v0.4.md`, `SOURCES.md` e `CHANGELOG.md`.

## Struttura

| File/cartella | Funzione |
|---|---|
| `server.py` | API locali, chiave, SQLite, file e integrazione gateway |
| `index.html` | Console e player, incluso client MediaSource locale |
| `ndi/native.py` | Caricamento runtime, discovery, frame-sync, buffer audio/video |
| `ndi/gateway.py` | Encoder FFmpeg, segmenti, watchdog, condivisione sorgenti |
| `diagnose_ndi.py` | Controllo installazione senza modificare il sistema |
| `data/` | Creato all'avvio: database, asset, chiave e segmenti temporanei |
| `runtime/`, `bin/` | Note per dipendenze native, nessun binario incluso |
| `tests/` | Test automatici; fixture ABI esplicitamente non-NDI |

I vecchi rapporti QA sono conservati solo come storico delle versioni precedenti.

## Carisma Prompt / gobbo elettronico (v0.7-alpha)

Apri `/prompt.html` dalla regia per caricare TXT/DOCX, creare cue, configurare i tre preset di font/dimensione/colori, controllare lo scroll manuale e abbinare player PRIMARY/BACKUP. Il modulo riceve anche OSC UDP (porta 9000 nell'avvio LAN) ed e' pensato per QLab e controller jog/shuttle USB. Vedi `LEGGIMI_PROMPT_v0.7.md`.

## Controller AJAZZ AKP03E — v0.8-alpha
Carisma Prompt puo usare direttamente AKP03E via USB HID. Vedi `LEGGIMI_AKP03E_v0.8.md`. La dipendenza runtime e `hidapi==0.15.0`; non serve lasciare aperto il software AJAZZ. Il controller usa credenziali proprie e puo ricadere su OSC in una configurazione Core ridondata.
