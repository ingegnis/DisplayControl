# Aggiornamento cumulativo 0.9.0-alpha

Base: pacchetto completo Carisma Display Control 0.8-alpha AKP03E.

1. Ferma server e controller e conserva un backup privato dell'installazione, in particolare `data/`.
2. Estrai la patch nella cartella che contiene `server.py`, sovrascrivendo i file dell'applicazione. La patch non contiene `data/`, chiavi o `Config_Locale.bat` e non richiede di cancellarli.
3. Riavvia il server e il controller. Ricarica tutte le pagine Prompt di regia e player; non mescolare versioni 0.8 e 0.9.
4. Verifica prima su un copione di prova JOG, velocità, pause, cue, blackout e continuità dopo arresto/riavvio del server.
5. In Impostazioni inserisci nome e logo e scegli se applicare il tema suggerito.

Per tornare alla versione precedente ripristina il backup completo, compresa la cartella dati. La nuova tabella di deduplicazione è aggiunta automaticamente al database; non contiene password amministrative.

Il pacchetto completo contiene sorgenti e test, senza binari FFmpeg/NDI o dipendenze HID già installate. Leggi README.md e TEST_REPORT.md per i limiti. La versione rimane alpha e il collaudo hardware è ancora necessario.
