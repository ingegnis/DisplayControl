# Aggiornamento cumulativo 0.10.0-alpha

La patch copre la versione completa 0.8-alpha AKP03E e la 0.9. Contiene anche
sincronismo e personalizzazione introdotti nella 0.9. Conserva un backup privato
dell'installazione e della cartella `data/` prima di aggiornare.

1. Ferma server e tutte le vecchie istanze controller.
2. Estrai la patch nella cartella contenente `server.py`, sovrascrivendo i file dell'applicazione.
3. Esegui `Installa_Controller_Windows.bat` o `sh Installa_Controller_Linux_Mac.sh`:
   Neo usa Pillow oltre a hidapi; le dipendenze sono isolate in `.controller-venv/`.
4. Se avevi già abbinato il servizio AKP03E non ripetere il pairing. Per una nuova
   postazione esegui la configurazione una volta, con un codice generato in Prompt.
5. Riavvia il server e avvia il controller unificato. Ricarica le pagine regia/player.
6. Chiudi i software dei produttori per evitare uso concorrente o macro duplicate.
7. Collega un modello supportato. Per il collaudo fisico usa CONTROLLERS.md.

La patch non contiene `data/`, token, database, ambienti virtuali, configurazioni
locali o binari dei fornitori. Non richiede di cancellarli. I vecchi nomi degli
avvii AKP03E restano compatibili e usano lo stesso servizio e la stessa configurazione.

Il pacchetto completo permette una nuova installazione, ma non trasferisce copioni,
credenziali o media della tua installazione. Non aggiornare durante uno spettacolo.
Il collaudo dei controller fisici non è stato eseguito qui: la release resta alpha.
