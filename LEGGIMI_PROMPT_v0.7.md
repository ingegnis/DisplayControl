# Carisma Prompt v0.7-alpha

Modulo gobbo elettronico locale per Carisma Display Control.

## Obiettivo

Il copione viene sincronizzato integralmente sui player palco. Durante lo spettacolo il server invia solo stato e comandi; lo scorrimento avviene localmente sul player. Se la LAN o il server si interrompono dopo la sincronizzazione, il player mantiene il copione e continua lo scroll con l'ultimo stato noto. La prima sincronizzazione richiede il server.

Questa versione e' una alpha da collaudare con un PRIMARY e un BACKUP prima dell'uso in spettacolo.

## Installazione dalla v0.5.2

1. Ferma il server e fai una copia della cartella corrente.
2. Copia la patch v0.7 nella cartella che contiene `server.py`, accettando sostituzioni e unione delle sottocartelle.
3. Non cancellare `data/`, `bin/`, `.setup/` o `Config_Locale.bat`.
4. Avvia `Avvia_Server_LAN_Windows.bat` oppure `Avvia_Server_LAN_Linux.sh`.
5. Apri `http://IP-DEL-SERVER:8787/prompt.html`.

Il database Prompt viene creato nello stesso SQLite del progetto senza rimuovere le configurazioni Display esistenti.

## Copione e cue

Sono supportati TXT e DOCX. Per creare un cue inserisci una riga:

```
[[CUE: SCENA BALCONE]]
```

Il cue punta alla prima riga successiva. Per automazioni OSC preferire cue nominati e stabili, non la sola posizione relativa.

## Aspetto: tre opzioni per voce

Per evitare configurazioni difficili da replicare, ogni voce e' limitata a tre preset:

- Font: **Sans classico**, **Sans largo**, **Serif**.
- Dimensione: **Medio**, **Grande**, **Extra grande**.
- Colori: **Bianco su nero**, **Ambra su nero**, **Nero su bianco**.

La reading line resta al 38% dell'altezza. Il player usa unita' relative all'altezza dello schermo (vh) per rendere la velocita' coerente su display con risoluzioni diverse.

## Controllo manuale / controller USB

La regia accetta queste scorciatoie quando il cursore non e' in un campo di testo:

| Comando | Tasto |
|---|---|
| Play / pausa | `Space` |
| Cue precedente | `Left` |
| Cue successivo | `Right` |
| Jog fine indietro | `J` |
| Jog fine avanti | `L` |
| Blackout | `B` |
| Torna in testa | `Home` |
| Shuttle avanti, 5 zone | `1` ... `5` |
| Shuttle al centro / stop | `0` |
| Shuttle indietro, 5 zone | `Shift+1` ... `Shift+5` |

### Specifica minima consigliata del controller

Per Carisma non serve un SDK proprietario: il controller deve poter emettere scorciatoie da tastiera tramite il proprio driver.

Requisiti consigliati:

- USB cablato, non Bluetooth.
- Jog wheel a rotazione libera per gli impulsi fini.
- Shuttle ring con ritorno a molla al centro e almeno 5 zone per direzione.
- Almeno 5 pulsanti programmabili.
- Driver che permetta profili per applicazione e combinazioni con Shift.
- Possibilita' di esportare/importare la mappatura del profilo.

Mappatura consigliata per un controller a 5 pulsanti:

1. `Space` - play/pausa
2. `Left` - cue precedente
3. `Right` - cue successivo
4. `B` - blackout
5. `Home` - top

Jog sinistra/destra -> `J` / `L`.
Shuttle zone avanti 1..5 -> `1`..`5`.
Shuttle centro -> `0` (velocita zero).
Shuttle zone indietro 1..5 -> `Shift+1`..`Shift+5`.

Il riferimento economico scelto per il progetto e' **Contour Shuttle Xpress** (5 pulsanti + jog/shuttle). La variante con piu' tasti e' **Shuttle PRO v2** (15 pulsanti + jog/shuttle). La compatibilita' e la mappatura del driver vanno provate sulla postazione Windows effettiva prima dello spettacolo.

## OSC / QLab

Il listener Carisma Prompt usa **OSC via UDP**, porta predefinita **9000**. L'avvio LAN lo espone sulla LAN; l'avvio locale normale resta su loopback.

Configurazione facoltativa in `Config_Locale.bat`:

```bat
set "CARISMA_PROMPT_OSC_PORT=9000"
set "CARISMA_PROMPT_OSC_ALLOW=192.168.1.50"
```

`CARISMA_PROMPT_OSC_ALLOW` puo' contenere piu' IP separati da virgola. In produzione e' consigliato limitare il listener all'IP del Mac QLab e degli eventuali controller OSC fidati.

Comandi implementati:

```text
/carisma/prompt/play
/carisma/prompt/pause
/carisma/prompt/toggle
/carisma/prompt/stop
/carisma/prompt/speed 0.12
/carisma/prompt/speed/delta 0.02
/carisma/prompt/jog 0.10
/carisma/prompt/top
/carisma/prompt/cue/<id>
/carisma/prompt/cue "id"
/carisma/prompt/cue/next
/carisma/prompt/cue/prev
/carisma/prompt/blackout 1
/carisma/prompt/message "5 MINUTI"
/carisma/prompt/message/clear
```

In QLab crea un Network Output Patch verso l'IP del server Carisma, UDP, porta 9000. Poi usa Network Cues con messaggi OSC personalizzati.

Per cue critici preferisci:

```text
/carisma/prompt/cue/scena-balcone
```

rispetto a `cue/next`: un cue assoluto e' idempotente, quindi un eventuale doppio invio UDP non fa avanzare di due scene.

OSC UDP non include conferma di consegna. Il server registra l'ultimo comando OSC ricevuto, ma l'operatore deve mantenere il controller manuale disponibile come override.

### Firewall Windows

Apri UDP 9000 solo sulla rete privata e, se possibile, solo dal computer QLab. Esempio PowerShell amministratore:

```powershell
New-NetFirewallRule -DisplayName "Carisma Prompt OSC" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 9000 -Profile Private -RemoteAddress 192.168.1.50
```

Sostituisci l'IP d'esempio con quello reale. Non esporre la porta su Internet.

## PRIMARY + BACKUP

Carisma Prompt prevede due ruoli per ogni stazione palco:

- `PRIMARY`
- `BACKUP`

Genera due codici separati dalla pagina Prompt e abbina due player distinti. Entrambi ricevono l'intero copione e lo stesso stato operativo. La regia mostra online/offline, versione del progetto, differenza di posizione e `HOT BACKUP PRONTO` quando il backup e' online e ha la stessa versione del copione.

### Backup professionale consigliato

Il backup software non puo' riparare un alimentatore, un cavo HDMI o un pannello guasto. La configurazione consigliata e':

- due player fisici distinti;
- due alimentatori distinti;
- due cavi Ethernet;
- preferibilmente server, switch e regia sotto UPS;
- **opzione A, massima affidabilita': due monitor palco**, uno PRIMARY e uno BACKUP;
- **opzione B: un monitor con due ingressi HDMI**, PRIMARY e BACKUP gia' collegati, con commutazione manuale immediata;
- per produzioni critiche, uno switch HDMI professionale con bypass/manual override puo' sostituire il cambio ingresso del monitor.

Non mettere PRIMARY e BACKUP sulla stessa microSD, sullo stesso alimentatore o sulla stessa uscita HDMI: annullerebbe gran parte della ridondanza.

Anche la regia puo' essere ridondata: lo stato vive sul server, quindi un secondo PC autorizzato puo' aprire `prompt.html`. Per non avere un singolo punto di guasto sul controllo manuale, tieni una tastiera o un secondo controller USB pronto sulla postazione di backup.

## Player Raspberry v0.7

Il generatore Raspberry v0.7 permette di scegliere al primo setup:

- Display / Digital Signage
- Prompt / Gobbo elettronico

Per Prompt, la pagina di visualizzazione e' inclusa localmente nella SD. L'identita' e il copione sincronizzato vengono conservati sul player; durante una perdita LAN la pagina locale rimane disponibile e il motore continua l'ultimo scroll noto.

La persistenza reale della cache Chromium dopo blackout, l'accelerazione video/HDMI e il boot su Pi fisico restano prove di collaudo sul tuo hardware. Il primo test va fatto su una sola SD.

## Procedura di collaudo consigliata

1. Carica un copione di prova con almeno 10 cue.
2. Abbina PRIMARY e BACKUP su due browser/PC prima di usare i Raspberry.
3. Verifica play/pausa, jog, 5 velocita' avanti/indietro, cue e blackout.
4. Invia cue assoluti da QLab/OSC.
5. Stacca la LAN del PRIMARY durante lo scroll: il testo deve continuare localmente.
6. Conferma che il BACKUP sia gia' sullo stesso cue e che la regia lo indichi pronto.
7. Riporta la LAN e verifica il riallineamento.
8. Ripeti con Raspberry e poi con un vero blackout elettrico.
9. Prima dell'uso in spettacolo esegui una prova prolungata e conserva controller manuale + copia cartacea/digitale di emergenza.

## Stato delle verifiche di questa consegna

Vedi `QA_PROMPT_v0.7.md`. Sono stati provati parser, import DOCX/TXT, pairing, ruoli PRIMARY/BACKUP, comandi e listener UDP OSC reale sul loopback. Il browser via HTTP reale e l'hardware palco non erano raggiungibili dall'ambiente di sviluppo, quindi non sono dichiarati collaudati.
