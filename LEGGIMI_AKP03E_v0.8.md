# Carisma Prompt v0.8-alpha — AJAZZ AKP03E diretto USB HID

## Obiettivo
Questa versione integra AJAZZ AKP03E (USB VID:PID `0300:3002`) come superficie di controllo nativa per Carisma Prompt. Durante lo show **non serve il software AJAZZ**: il servizio `akp03e_controller.py` parla direttamente con il dispositivo USB HID e invia comandi a Carisma con credenziali dedicate e limitate.

Il protocollo e stato implementato sulla base di specifiche pubbliche e confrontato con implementazioni open source gia verificate su hardware. Il dispositivo dell'utente NON e stato fisicamente raggiunto in questo ambiente: la prova USB reale resta necessaria.

## Mapping predefinito

### Sei tasti LCD
| LCD | Azione | Stato dinamico |
|---|---|---|
| 1 | PLAY / PAUSA | icona cambia PLAY ↔ PAUSA |
| 2 | CUE precedente | fissa |
| 3 | CUE successivo | fissa |
| 4 | BLACKOUT | icona segnala BLACK ON |
| 5 | TOP | torna all'inizio |
| 6 | TAKE PRIMARY/BACKUP | mostra TAKE B, TAKE A, oppure N/R se il ramo richiesto non e pronto |

### Tre encoder premibili
| Encoder | Rotazione | Pressione |
|---|---|---|
| Grande / 0 | velocita ±0,015 vh/s per scatto | PLAY/PAUSA |
| 1 | jog fine ±0,08 vh | STOP |
| 2 | cue precedente/successivo | TAKE A/B |

### Tre pulsanti non LCD
- 7: cancella messaggio rapido
- 8: STOP
- 9: TAKE A/B

Il servizio applica debounce agli eventi meccanici e si riconnette automaticamente se il controller USB viene scollegato e ricollegato.

## Installazione Windows
1. Applica la patch v0.8 al server Carisma v0.7 e riavvia `Avvia_Server_LAN_Windows.bat`.
2. In `prompt.html`, pannello **AJAZZ AKP03E**, premi **Genera codice controller**.
3. Sul PC di regia esegui `Installa_Controller_AKP03E_Windows.bat`. Installa, solo se manca, `hidapi==0.15.0` come wheel binaria.
4. Collega l'AKP03E via USB-C.
5. Esegui `Test_Controller_AKP03E_Windows.bat`: i sei LCD mostrano il layout Carisma e per 12 secondi vengono stampati tasti/encoder rilevati.
6. Esegui `Configura_Controller_AKP03E_Windows.bat`, inserisci indirizzo Carisma e il codice a otto cifre.
7. Avvia `Avvia_Controller_AKP03E_Windows.bat` prima dello show.

La configurazione e il token del controller sono salvati in `data/akp03e_controller.json`; non condividere il file. Il token **non e la chiave amministratore** e non permette di cambiare il copione o amministrare il server.

## LCD e rotazione
AKP03E usa sei immagini JPEG 60x60. La consegna include gia tutte le icone in quattro rotazioni. Il default e `270`, coerente con una implementazione Python verificata su AKP03E reale. Se sul tuo esemplare le scritte risultano ruotate, modifica `iconRotation` in `data/akp03e_controller.json` scegliendo `0`, `90`, `180` o `270`; non serve rigenerare immagini.

## Resilienza
Il file di configurazione accetta:

```json
{
  "servers": ["http://192.168.10.10:8787"],
  "oscTargets": ["192.168.10.11:9000", "192.168.10.12:9000"]
}
```

- `servers`: normalmente usa il VIP Carisma. Puo contenere piu endpoint HTTP; il servizio prova l'ultimo raggiunto e poi gli altri.
- `oscTargets`: fallback opzionale. Se nessun Core HTTP risponde, i comandi compatibili vengono inviati via OSC UDP a tutti gli endpoint elencati.

Il fallback OSC include PLAY, PAUSA, STOP, velocita, jog, cue, blackout e TAKE. Non sostituisce il quorum/cluster server: serve come ulteriore percorso di controllo durante una transizione HA.

Se il controller o il server smettono di rispondere, i player Prompt continuano lo scroll locale gia ricevuto. Il controller non e quindi nel percorso necessario per mantenere visibile un copione gia in esecuzione.

## TAKE PRIMARY/BACKUP
v0.8 introduce `activeRole` nel runtime e i comandi:

```text
/carisma/prompt/take/primary
/carisma/prompt/take/backup
/carisma/prompt/take "PRIMARY"
```

Il TAKE e per ora **logico**: registra quale ramo e considerato attivo, aggiorna regia e LCD e prepara l'integrazione con uno switch HDMI/GPIO/OSC. Non commuta fisicamente un ingresso HDMI da solo. Il PRIMARY e il BACKUP continuano a renderizzare in parallelo per restare hot mirror.

## Sicurezza
- pairing a 8 cifre, monouso, scadenza 10 minuti;
- token controller separato dall'amministratore;
- API controller con allow-list di comandi;
- nessuna possibilita di caricare/modificare copioni tramite token AKP03E;
- HTTP attuale destinato esclusivamente a LAN fidata, mai Internet.

## Dipendenze
Runtime controller: Python 3.11+ e `hidapi==0.15.0`. Nessuna dipendenza grafica e nessun software vendor. Le immagini LCD sono pre-generate.

## Fonti protocollo / verifica incrociata
- https://github.com/Aiacos/ajazz-control-center/blob/develop/docs/protocols/streamdeck/akp03.md
- https://github.com/tomekceszke/ajazz-akp03e
- https://github.com/mishamyrt/ajazz-sdk
- https://pypi.org/project/hidapi/

Questi progetti non sono componenti runtime di Carisma; `hidapi` e l'unica dipendenza installata.
