# DisplayControl

Regia locale per schermi informativi e gobbo elettronico, derivata da Carisma Display Control. **Versione 0.10.0-alpha**.

Console web, player browser, copioni TXT/DOCX, cue, controllo OSC e controller USB intercambiabili (AJAZZ, Contour, MSD-TWO e Stream Deck Neo). Il gateway opzionale riceve NDI sul server e lo converte con FFmpeg in video per i browser.

## Avvio

Richiede Python 3.9 o successivo. Il server e le API usano la libreria standard; non occorrono dipendenze Python per la console o il gobbo.

```sh
python server.py
```

Apri l'indirizzo stampato dal server e usa la chiave generata localmente. Su macOS/Linux il comando può essere `python3 server.py`. I dati vengono creati in `data/` e restano esclusi da Git.

- Console: `/`
- Gobbo/regia: `/prompt.html`
- Player gobbo: `/prompt_player.html`
- Monitor schermi: `/monitor.html`
- Abbinamento player signage: `/players.html`

Per una prova LAN esplicita: `python server.py --host 0.0.0.0`. La versione attuale usa HTTP su rete fidata; non pubblicare il server su Internet. Scaricare questo progetto da casa non richiede di esporre la regia.

## Personalizzazione

In **Impostazioni** inserisci il nome dell'organizzazione e carica un logo PNG, JPEG o WebP. L'immagine viene ridimensionata e salvata nel progetto; il software propone un tema derivato dal logo, che puoi scegliere di applicare. Il logo occupa un piccolo spazio nell'intestazione. Copioni, messaggi di spettacolo e uscite video non ricevono sovrimpressioni del logo.

Il nome sostituisce il marchio storico nell'interfaccia e nelle schermate dimostrative. Identificatori interni, percorsi OSC `/carisma/...`, nomi dei file e credenziali esistenti rimangono compatibili.

## Sincronismo del gobbo

Anteprima e player usano `prompt_shared.js`: stessa superficie virtuale 1280×720, stessi margini, font e interlinea. La finestra visualizza una versione scalata senza reimpaginare il testo. `offsetVh` e velocità fanno riferimento alla pagina virtuale, non alle dimensioni fisiche della finestra. La sequenza dei comandi impedisce di applicare risposte vecchie; lo scorrimento locale usa un orologio monotono e prosegue durante l'assenza del server.

**Dopo l'aggiornamento riavvia il server e ricarica tutte le pagine Prompt. Non mescolare regia/player 0.8 e 0.9.** Per il confronto su sistemi operativi diversi va verificata anche la disponibilità dei font di sistema.

## Controller automatici e dipendenze facoltative

- Windows: `Installa_Controller_Windows.bat`, poi `Configura_Controller_Windows.bat` una sola volta e `Avvia_Controller_Windows.bat`.
- macOS/Linux: `sh Installa_Controller_Linux_Mac.sh`, poi `sh Avvia_Controller_Linux_Mac.sh --setup` e `sh Avvia_Controller_Linux_Mac.sh`.
- Il servizio riconosce automaticamente AJAZZ AKP03E, Contour ShuttleXpress/PRO v2, Mars Gaming MSD-TWO ed Elgato Stream Deck Neo. Puoi alternarli senza rifare il pairing; la pagina Prompt può essere chiusa o in secondo piano. Dettagli, comandi, permessi e limiti in [CONTROLLERS.md](CONTROLLERS.md).
- Gli installer usano un ambiente `.controller-venv/` isolato con hidapi e Pillow; il servizio richiede Python 3.11+. Server e gobbo mantengono i requisiti precedenti. I vecchi avvii AKP03E inoltrano al servizio unificato.
- Ogni Core può essere abbinato separatamente, con il proprio token. Questo non replica database, copioni o stato e non implementa un cluster HA.
- Il fallback OSC è opzionale e non conferma la ricezione. Un esito HTTP ambiguo non causa la ripetizione automatica di comandi relativi; un rifiuto di autenticazione non viene aggirato con OSC.
- Per NDI installa separatamente FFmpeg e il runtime NDI ufficiale. I binari e le licenze dei fornitori non sono inclusi. Leggi `LEGGIMI_NDI.md` e `LEGGIMI_SETUP_WINDOWS_v0.4.1.md`.
- I sorgenti Android TV sono inclusi; non viene distribuito un APK collaudato.

## Test e limiti

```sh
python -m unittest discover -s tests -v
node tests/test_live_policy.js
node tests/test_branding.js
node tests/test_prompt_timeline.js
```

FFmpeg/ffprobe e un compilatore C servono alle prove di codifica e ABI simulata. In loro assenza alcuni test vengono saltati: controlla sempre il riepilogo.

La verifica di questa release ha completato **151 test Python senza errori o test saltati** e tre suite JavaScript. Sono inclusi scambio dei quattro tipi di controller con un solo pairing via HTTP reale, report HID sintetici e installazione pulita delle dipendenze. Le prove browser del motore Prompt della 0.9 restano documentate come tali. Dettagli in [TEST_REPORT.md](TEST_REPORT.md).

**Controller fisici, sorgente NDI reale, Raspberry/Chromecast, QLab, commutazione HDMI e cluster HA non sono certificati da queste prove.** TAKE cambia il ruolo logico, senza commutare ingressi HDMI. La release rimane alpha.

## Download da un altro PC

Da GitHub puoi usare **Code → Download ZIP**, oppure clonare questo repository. Il pacchetto contiene il software, non la tua installazione con credenziali, copioni e contenuti. Per trasferire anche il lavoro usa un backup privato di `data/`, tenendolo fuori dal repository pubblico.

## Pubblicazione e licenze

La prima pubblicazione esclude dati di esercizio, database, chiavi, configurazioni locali, log storici, cache, binari dei fornitori e materiale di firma. Le credenziali di prova presenti nei test sono valori sintetici.

Non è stata aggiunta una nuova licenza al codice del progetto. La pubblicazione del sorgente non sostituisce la scelta della licenza da parte del titolare. Le dipendenze e i riferimenti tecnici mantengono i propri termini; vedi `SOURCES.md`.
