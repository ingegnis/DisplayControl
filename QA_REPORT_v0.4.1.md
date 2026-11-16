> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Carisma 0.4.1 - Verifica della patch di installazione

Data: 29 ottobre 2026.
Ambiente: Linux x86_64, Python 3.13.5, FFmpeg installato nell'ambiente.

## Esito

**39 test automatici superati**, inclusi i 15 test gia presenti nella v0.4 e
24 test aggiunti per diagnosi/setup. Ultima esecuzione: 7,845 secondi.

Comando:

```
python -m unittest discover -s tests -v
```

## Che cosa e stato verificato

- Riconoscimento esatto dei nomi encoder, evitando falsi positivi nella descrizione.
- Errori espliciti per FFmpeg assente, processo fallito e timeout.
- **Conversione reale**, con FFmpeg Linux disponibile, di un secondo di video nero
  e audio silenzioso in MP4 frammentato H.264/AAC. Controllati avcC/mp4a/ftyp.
- Zero sorgenti NDI non trasforma un runtime disponibile in un'installazione fallita.
  Il runtime in questo test e una fixture, non una sorgente NDI fisica.
- Parsing checksum, riuso della cache senza download, blocco su hash discordante.
- Rifiuto URL HTTP e redirect HTTPS -> HTTP.
- Estrazione ZIP valida e rifiuto di path traversal, nomi duplicati con case
  diverso, link simbolici e archivi oltre i limiti di dimensione.
- Installazione FFmpeg in staging, conservazione build precedente e assenza di
  sostituzione quando il test della nuova build fallisce (processi simulati).
- Percorsi del progetto salvati in forma relativa; file di dati sentinella intatto.
- Riparazione con tutte le componenti presenti: nessuna installazione.
- **Caso del messaggio utente:** FFmpeg mancante, NDI presente; installazione
  FFmpeg invocata una volta e installazione NDI mai invocata (funzioni simulate).
- Runtime NDI mancante: installazione e ricontrollo selettivi (funzioni simulate).
- Nessun messaggio di successo se il controllo finale fallisce.
- Regressioni server/API e pipeline esistenti: suite v0.4 ancora superata.

## Verifica diagnostica diretta

Eseguito anche:

```
python diagnose_ndi.py --seconds 0 --smoke-test
```

Risultato: Python OK; FFmpeg H.264/AAC OK; conversione di prova OK; runtime NDI
ufficiale assente. Il comando ha restituito correttamente codice 1 e non ha
installato nulla. Non e stato trattato come un test NDI reale riuscito.

## Limiti da non confondere con un collaudo Windows

- Non sono disponibili Windows nativo, PowerShell Windows, Authenticode o UAC
  nell'ambiente: il bootstrap e gli installer sono stati revisionati nel codice,
  ma **non eseguiti su Windows**. Il loro collaudo va fatto sul PC dell'utente.
- Le prove di installazione selettiva e sostituzione usano fixture/mock per i
  download e i processi Windows. Non certificano l'eseguibile Windows FFmpeg.
- Non e stato possibile effettuare download HTTPS dal container (risoluzione
  DNS assente). Gli URL e le condizioni sono stati consultati tramite fonti web
  ufficiali; il setup deve verificare effettivamente hash/firma sul PC.
- Nessuna sorgente NDI fisica, decodifica HX/H.265 o prestazione NEXCOM certificata.
- L'interfaccia non e stata cambiata: questa e una patch del setup, non una nuova
  versione funzionale del player.

Per i limiti gia noti della v0.4 consultare anche `QA_REPORT_v0.4.md`.
