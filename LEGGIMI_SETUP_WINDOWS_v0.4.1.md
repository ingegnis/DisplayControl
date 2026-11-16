# Carisma 0.4.1 - Verifica e installazione automatica Windows

## Per il PC che ha gia Python e NDI

La correzione e per il caso segnalato: Python 3.14.7 a 64 bit e runtime NDI
6.2.1.0 presenti, FFmpeg mancante. Non reinstalla le componenti funzionanti.

1. Ferma il server Carisma prima di aggiornare i file.
2. Conserva una copia della cartella del progetto. Estrai la patch e copia TUTTO
   il suo contenuto nella cartella che contiene `server.py`, sostituendo i file
   omonimi e unendo la sottocartella `ndi`. Non eseguire il BAT dentro lo ZIP.
3. Fai doppio clic su `Verifica_NDI_Windows.bat`.
4. La procedura riconosce Python e NDI, scarica FFmpeg se manca, controlla il
   checksum SHA-256 pubblicato dal distributore, prova una conversione H.264/AAC
   e installa la build nella cartella del progetto.
5. Quando compare `DIPENDENZE: OK`, esegui `Avvia_Windows.bat`.
6. Nella console apri **Ingressi NDI**, prova il generatore locale, poi cerca
   una sorgente NDI accesa sulla LAN. Il generatore NON e una sorgente NDI reale.

La patch non include `data/` o `Config_Locale.bat` e il setup non li modifica.
Non cancella player, palinsesti, file caricati o chiavi del server.

## Cosa fanno i tre pulsanti di avvio

| File | Funzione |
|---|---|
| `Verifica_NDI_Windows.bat` | Verifica e ripara le dipendenze mancanti/non utilizzabili, poi ricontrolla. |
| `Solo_Verifica_NDI_Windows.bat` | Diagnosi senza download o installazioni; crea soltanto un file video temporaneo per il test codec, poi lo elimina. |
| `Avvia_Windows.bat` | Usa il Python e i percorsi salvati e avvia il server. Non installa FFmpeg o NDI; su un PC senza Python il bootstrap prova a predisporlo. |

Anche `python diagnose_ndi.py --smoke-test` rimane un comando di sola diagnosi.
La riparazione automatica e Windows x64; le istruzioni Debian non cambiano.

## Dipendenze gestite

### FFmpeg

- Riutilizza una build esistente se ha `libx264`, `aac` e supera il test video.
- Se serve, scarica la build Windows x64 **release essentials** da gyan.dev,
  distributore collegato dalla pagina ufficiale FFmpeg.
- Verifica SHA-256 prima di estrarre o avviare gli eseguibili. Un hash discordante
  blocca l'installazione: non viene ignorato.
- Usa `bin/ffmpeg/bin/ffmpeg.exe`, senza modificare PATH o registro di sistema.
- Mantiene licenza e documentazione incluse nel pacchetto del distributore.
- Prima di sostituire una build locale, prova la nuova in una cartella temporanea.
  Conserva la precedente in `bin/ffmpeg.backup-...`.
- I download completati e il checksum restano in `.setup/downloads/` e sono
  riutilizzabili. Non distribuiamo questi binari dentro la patch.

### Python

- Cerca un interprete >= 3.9 a 64 bit, con le librerie standard necessarie,
  nel PATH, nel launcher, nei percorsi salvati e nel registro Python.
- Il tuo Python 3.14.7 NON viene aggiornato o sostituito.
- Solo se manca un interprete compatibile, scarica l'installer x64 Python
  3.14.10 da python.org, controlla SHA-256 e firma del fornitore e lo installa
  per l'utente corrente senza cambiare PATH o launcher.
- La versione di bootstrap e fissata alla release verificata del 25 ottobre 2026;
  non e un servizio di aggiornamento continuo di Python.
- Non servono pacchetti `pip`, Chocolatey o WinGet per questo progetto.

### Runtime NDI

- Un runtime caricato correttamente e lasciato invariato.
- Se manca/non si carica e non c'e un'alternativa gia disponibile, scarica il
  redistributable dal collegamento ufficiale `https://ndi.link/NDIRedistV6`.
- Verifica la firma Authenticode e l'editore atteso prima di avviarlo.
- L'installer NDI resta visibile: leggi e accetta personalmente la licenza.
  Windows puo richiedere consenso UAC e credenziali di amministratore.
- Non accetta la licenza in silenzio, non reinstalla Windows, non disabilita
  antivirus/firewall e non riavvia il computer automaticamente.
- Se la firma non e valida, l'editore e cambiato, annulli l'installer o la DLL
  continua a non caricarsi, il setup dichiara l'errore e non stampa un successo.
- La ricerca di zero sorgenti in LAN e un AVVISO, non una dipendenza mancante:
  non provoca download o reinstallazioni inutili.

## Internet e funzionamento offline

Serve Internet per procurarsi le dipendenze assenti se non sono gia nella cache.
Una volta predisposte, le normali verifiche sulle componenti presenti e il server
non richiedono Internet. La ricerca/ricezione NDI usa la LAN.
Per la prima installazione su un PC isolato prepara prima i pacchetti su un PC
connesso; copiare il solo ZIP Carisma non include Python, FFmpeg o NDI.
La verifica della firma degli installer puo richiedere che Windows abbia le
catene di certificazione/validita aggiornate. Non si aggira un controllo fallito.

## File creati dal setup

```
.setup/
  python-path.txt        Interprete scelto dal bootstrap
  dependencies.json     Percorsi verificati di FFmpeg/NDI
  install.log           Registro della riparazione, con rotazione
  install.lock          Blocco contro due riparazioni simultanee
  downloads/            Pacchetti e checksum scaricati
bin/
  ffmpeg/               Build locale completa e documentazione
```

I percorsi interni al progetto sono registrati in forma relativa. Quelli esterni
(Python/NDI gia installati) restano assoluti. `Avvia_Windows.bat` carica i percorsi
verificati da `dependencies.json`, con precedenza per questa sola applicazione;
`Config_Locale.bat` non viene riscritto e le variabili globali non vengono cambiate.
Per tornare alla scelta manuale, a server fermo rinomina
`.setup/dependencies.json` e imposta i tuoi percorsi in `Config_Locale.bat`.
Una cartella di progetto spostata da un altro PC verra ricontrollata.

## Errori senza interventi distruttivi

- **Download interrotto:** il file parziale viene eliminato, la build precedente
  non e toccata; puoi rilanciare la verifica.
- **Certificato/hash non valido:** blocco esplicito. Non bypassare il controllo.
- **Cartella non scrivibile:** usa una tua cartella, ad esempio sotto Documenti;
  per installare FFmpeg non e necessario avviare tutto come amministratore.
- **Policy PowerShell aziendale:** il BAT usa una policy per il solo processo,
  senza cambiare la policy del computer. Se una policy gestita lo blocca,
  rivolgiti all'amministratore, non disabilitare le protezioni.
- **NDI installato ma non funzionante:** viene mostrato il dettaglio della DLL;
  possibili incompatibilita o componenti di sistema mancanti non si risolvono
  dichiarando un successo. Dopo un eventuale riavvio richiesto, ripeti la prova.
- **Nessuna sorgente NDI:** accendi un trasmettitore e verifica subnet/firewall;
  il setup non apre porte e non disabilita il firewall automaticamente.

## Verifiche effettivamente eseguite

Vedi `QA_REPORT_v0.4.1.md`. Test automatici su logica, file, regressioni del server
e conversione FFmpeg reale. L'ambiente di sviluppo non e Windows: bootstrap
PowerShell, Authenticode, UAC e installer nativi restano da collaudare sul PC.
Nessun collaudo di sorgente NDI fisica viene dichiarato da questo aggiornamento.

## Fonti dei download e dei parametri

- FFmpeg: https://ffmpeg.org/download.html
- Build Windows: https://www.gyan.dev/ffmpeg/builds/
- SHA-256 build: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256
- Python bootstrap: https://www.python.org/downloads/release/python-31410/
- Uso Python Windows: https://docs.python.org/3.14/using/windows.html
- Runtime NDI: https://docs.ndi.video/all/developing-with-ndi/sdk/dynamic-loading-of-ndi-libraries
- Installazione/licenza NDI: https://docs.ndi.video/all/developing-with-ndi/sdk/software-distribution

Link e parametri consultati il 29 ottobre 2026. I download FFmpeg/NDI possono
cambiare a monte; hash e firma sono controllati sul PC al momento dell'esecuzione.
