> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Rapporto di verifica - v0.1.0

## Verifiche eseguite

- Parsing del JavaScript con Node e compilazione del Python.
- Rendering della console desktop e mobile in Chromium. Nessun errore JavaScript rilevato durante i percorsi verificati; nessun overflow orizzontale a 390 px nella vista Schermi.
- Navigazione fra Schermi, Contenuti, Playlist, Palinsesti, Diagnostica e Impostazioni.
- Assegnazione di un contenuto, creazione di una schermata, aggiunta di una postazione e salvataggio di un palinsesto.
- Regola settimanale che supera mezzanotte, con valutazione corretta del giorno di inizio.
- API reali del server: autenticazione, conflitti di revisione, rifiuto di payload non validi, restrizione dei MIME caricabili, calcolo SHA-256, download identico al file caricato, validazione degli ID e heartbeat.
- Scrittura effettiva dei dati in SQLite e conservazione della configurazione dopo il riavvio del server. I sei test automatici del server inclusi nel pacchetto sono passati.
- Player collegato alle API reali attraverso il banco di prova: ricezione dei comandi, mantenimento del programma durante l'isolamento simulato e applicazione dell'aggiornamento alla riconnessione.
- Riproduzione effettiva di un video MP4 locale nel renderer: i fotogrammi decodificati sono passati da 5 a 35 mentre le richieste alle API erano rese indisponibili.
- Sorgente NDI dimostrativa: fallback esplicito, senza fingere la ricezione di un flusso.
- Aggiornamento incompleto: un file assente ha impedito la sostituzione del programma valido.

## Metodo e limiti

Il renderer di questa sessione non consente la navigazione verso file o URL locali. Per verificare l'interfaccia sono stati quindi usati il documento HTML effettivo, un adattatore di memoria per localStorage/IndexedDB e un ponte verso le API HTTP reali del server. Questi adattatori appartengono esclusivamente al banco di prova e **non sono inclusi nell'app consegnata**.

Le verifiche dimostrano il comportamento dell'interfaccia, delle API e della logica di continuita del player nelle condizioni provate. **Non sostituiscono un collaudo del salvataggio nativo del browser, del service worker o del riavvio offline sul PC dell'utente.** Queste prove vanno effettuate con il pacchetto locale usando le istruzioni del README.

Non sono stati provati NEXCOM, Debian installato, Chromecast G454V, bootloader, accelerazione hardware del mini PC, fonti NDI reali, recupero dopo blackout, sincronismo di videowall o funzionamento continuativo per 24 ore. Il gateway NDI e l'app Android non fanno parte di questa versione.
