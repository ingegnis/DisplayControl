# Controller intercambiabili — 0.10.0-alpha

Un unico servizio sulla postazione di regia riconosce i modelli supportati, legge
direttamente i report USB HID e invia i comandi all'API Prompt con un token limitato.
La pagina Prompt può restare in secondo piano o essere chiusa. Server e servizio
controller devono restare in esecuzione; non si tratta di un firmware installato
nel controller né di un servizio Windows eseguito prima dell'accesso utente.

## Modelli implementati

| Controller | Identità USB | Ingresso | LCD |
|---|---|---|---|
| AJAZZ AKP03E | `0300:3002` | Protocollo AKP 3, eventi con stato | 6 tasti |
| AJAZZ AKP03E, altra revisione | `0300:1002` | Protocollo AKP 2, clic discreti | 6 tasti |
| Mars Gaming MSD-TWO | `0b00:1001` | Protocollo AKP 2, clic discreti | 6 tasti |
| Contour ShuttleXpress | `0b33:0020` | Ghiera, jog e 5 pulsanti | Nessuno |
| Contour ShuttlePRO v2 | `0b33:0030` | Ghiera, jog e 15 pulsanti | Nessuno |
| Elgato Stream Deck Neo | `0fd9:009a` | 8 tasti e 2 tasti touch | 8 tasti |

**Sono integrazioni software alpha, verificate con report sintetici e trasporti
simulati. Nessuno di questi controller è stato collaudato fisicamente qui.** Il
riconoscimento usa VID/PID e interfacce, non la sola somiglianza del nome. Altre
revisioni con identificativi o firmware diversi richiedono una verifica dedicata.
Tastiere e dispositivi sconosciuti non vengono aperti come controller.

## Prima installazione

Su Windows:

1. Esegui `Installa_Controller_Windows.bat`. Crea `.controller-venv/` e installa
   `hidapi` e Pillow nell'ambiente isolato, senza modificare Python di sistema.
2. Nella regia Prompt genera il codice controller. Esegui
   `Configura_Controller_Windows.bat` e inserisci indirizzo del Core e codice.
3. Avvia `Avvia_Controller_Windows.bat`; puoi minimizzare la finestra.
4. Collega uno dei controller: viene riconosciuto senza scegliere il modello.

Su macOS/Linux, con Python 3.11 o successivo:

```sh
sh Installa_Controller_Linux_Mac.sh
sh Avvia_Controller_Linux_Mac.sh --setup
sh Avvia_Controller_Linux_Mac.sh
```

L'abbinamento riguarda il servizio sul PC, non il singolo controller. Una
configurazione 0.9 già abbinata viene riutilizzata da
`data/akp03e_controller.json`: non occorre rigenerare i token per cambiare hardware.
Le credenziali non vengono incorporate nei dispositivi né pubblicate nel repository.

I vecchi avvii `*_AKP03E_*` e `python akp03e_controller.py` inoltrano al servizio
unificato. Ferma la vecchia istanza prima dell'aggiornamento. Il blocco del file
di configurazione impedisce due istanze della nuova versione sulla stessa
configurazione e si libera alla chiusura del processo.

Chiudi i software di controllo AJAZZ/Mars/Elgato/Contour durante l'uso diretto,
per evitare che tengano occupata l'interfaccia o generino anche macro tastiera.
Su Linux può servire installare manualmente `99-displaycontrol-controllers.rules`
in `/etc/udev/rules.d/`, ricaricare udev e ricollegare il dispositivo. Su macOS
verifica eventuali autorizzazioni HID richieste dal sistema; non vengono modificate
automaticamente. Non vengono usati hook globali della tastiera.

L'avvio automatico Windows rimane opzionale:
`Installa_Avvio_Automatico_Controller_Windows.bat` riutilizza la voce di avvio
precedente, evitando un secondo avvio parallelo. Non viene installato eseguendo
semplicemente il programma o applicando la patch.

## Cambio controller e uso contemporaneo

Puoi scollegare AJAZZ e collegare Contour, MSD-TWO o Neo senza riavviare il
servizio, cambiare copione o rifare il pairing. La scansione avviene ogni secondo;
gli errori di apertura vengono ritentati dopo due secondi. I tempi reali dipendono
anche da sistema operativo, disponibilità dell'interfaccia e aggiornamento LCD.

Possono restare collegati più controller, fino a otto interfacce supportate:
i comandi vengono serializzati e vale l'ultima azione effettivamente eseguita.
Il riconoscimento da solo non avvia né ferma il testo. Scollegare un controller
lascia continuare lo scorrimento; centrare la ghiera Contour invia invece STOP.
Per armare una ghiera collegata fuori centro, riportala prima al centro.

Nella regia **Controller USB** mostra i modelli che il servizio comunica come
collegati. Le informazioni di stato non includono percorsi USB o numeri seriali.

## Comandi

AJAZZ e MSD-TWO mantengono la stessa disposizione:

| Controllo | Azione |
|---|---|
| LCD 1–6 | PLAY/PAUSA, cue precedente, cue successivo, blackout, TOP, TAKE A/B |
| Manopola 1 | Velocità; pressione PLAY/PAUSA |
| Manopola 2 | Jog; pressione STOP |
| Manopola 3 | Cue precedente/successivo; pressione TAKE A/B |
| Tasti laterali 1–3 | Cancella messaggio, STOP, TAKE A/B |

Su Neo i primi sei LCD hanno le stesse azioni; LCD 7 e 8 diminuiscono e aumentano
la velocità. I due tasti touch fanno jog indietro e avanti. Le immagini sono
convertite al formato JPEG 96×96 del Neo; InfoBar non viene personalizzata.

Su Contour la ghiera imposta sette velocità per verso, con STOP al centro; il
jog interno sposta il testo. I primi cinque pulsanti sono PLAY/PAUSA, cue −,
cue +, blackout e TOP. Su PRO v2, pulsanti 6–9: TAKE, cancella messaggio, STOP,
TAKE; pulsanti 10–15: PLAY, PAUSA, STOP, velocità −, velocità +, TAKE BACKUP.
La numerazione fisica va confermata con la diagnosi sul dispositivo.

PLAY dopo STOP o dopo il caricamento di un copione avvia una velocità iniziale
di 0,11 pagine virtuali/s quando la velocità era zero. PAUSA conserva la velocità.
I passi degli encoder sono gli stessi della versione precedente.

## Diagnosi prima dell'uso

Ferma il servizio e apri `Test_Controller_Windows.bat`, oppure:

```sh
sh Avvia_Controller_Linux_Mac.sh --list
sh Avvia_Controller_Linux_Mac.sh --diagnose --seconds 30
```

La diagnosi legge gli eventi senza inviare comandi al server. Verifica ogni
pulsante/manopola, centratura Contour, orientamento LCD, scollegamento e
riconnessione. Poi prova su un copione di test con la pagina Prompt chiusa e
il player aperto. Non usare il primo collaudo durante uno spettacolo.

## Resilienza e limiti

I comandi hanno una scadenza di 750 ms in coda. Le code sono limitate; STOP
ha priorità. Gli eventi di una vecchia connessione non vengono applicati a
una successiva riconnessione. Il polling dello stato e gli heartbeat usano un
thread separato: non bloccano la lettura USB né la coda comandi. Una richiesta
HTTP già in corso può comunque ritardare il comando successivo; non è un
arresto hardware in tempo reale.

Il fallback e i token per Core restano quelli della 0.9. Un timeout ambiguo
non causa la ripetizione dei comandi relativi; un rifiuto HTTP non viene aggirato
con OSC. UDP non conferma la consegna e il cambio endpoint non replica i Core.

Le prove locali comprendono tutti i protocolli e il passaggio attraverso una
vera API HTTP con un solo pairing, ma non USB reale, driver concorrenti, permessi
macOS/Linux, firmware, orientamento dei display o latenza sul palco.

## Riferimenti di protocollo

Implementazione indipendente dei formati e delle identità USB; nessun driver
esterno viene copiato nel progetto o eseguito dai controller. Consultati il
16 novembre 2026:

- [Mars Gaming MSD-TWO — produttore](https://marsgaming.eu/en/control-decks/msd-two)
- [Tabella delle identità AKP/MSD e protocolli](https://github.com/tommybobb/crabdeck/blob/master/devices.py)
- [Protocollo MSD-TWO e clic discreti](https://github.com/tommybobb/crabdeck/blob/master/deck.py)
- [Lettore degli stati Mirajazz](https://github.com/4ndv/mirajazz/blob/main/src/state.rs)
- [Identità e report Contour — LinuxCNC](https://github.com/LinuxCNC/linuxcnc/blob/master/src/hal/user_comps/shuttle.c)
- [Formati Stream Deck Neo](https://github.com/abcminiuser/python-elgato-streamdeck/blob/master/src/StreamDeck/Devices/StreamDeckNeo.py)
- [Identità USB Elgato](https://github.com/abcminiuser/python-elgato-streamdeck/blob/master/src/StreamDeck/ProductIDs.py)

Gli autori dei riferimenti non certificano questa integrazione. Versioni delle
dipendenze per una nuova installazione: hidapi 0.15.0, Pillow 13.0.0.
