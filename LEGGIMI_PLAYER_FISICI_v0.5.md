# Carisma Display Control v0.5-alpha — collegamento dei player fisici

## Stato reale della consegna

Questa versione aggiunge **abbinamento, credenziali distinte per player, accesso limitato ai contenuti assegnati e avvio server in LAN**. Il player browser, la console di abbinamento e la pipeline FFmpeg sono stati verificati nei limiti descritti nel rapporto QA.

**Per Chromecast Google TV HD G454V sono inclusi i sorgenti del player Android TV e gli script di compilazione/installazione. Non e incluso un APK gia compilato.** Nell'ambiente di sviluppo disponibile mancavano l'SDK Android, l'accesso per scaricarlo e un Chromecast collegato. La classe Java delle regole di rete e stata compilata e testata; la Activity Android completa, il suo APK e l'installazione Windows/ADB NON sono stati eseguiti.

Non chiamare questa versione un sistema gia collaudato in teatro o pronto 24/7. Non vengono modificati bootloader, firmware, launcher Google, firewall o account sul dispositivo.

## 1. Aggiornare senza perdere il progetto v0.4.1

1. Arresta il server Carisma e fai una copia della cartella attuale.
2. Per la **patch**, copia tutto il suo contenuto nella cartella che contiene `server.py`, sostituendo i file richiesti. Non eseguirla nello ZIP.
3. La patch NON contiene `data/`, `bin/ffmpeg`, `.setup/` o `Config_Locale.bat`: non sovrascrive i tuoi dati o i binari installati. Le nuove tabelle SQLite si aggiungono al primo avvio.
4. In alternativa, estrai il progetto completo in una cartella nuova e, a server fermo, trasferisci dalla vecchia cartella `data/`, `bin/`, `.setup/` e `Config_Locale.bat` quando presenti. Le credenziali e i file media sono riservati: non condividere queste cartelle.

## 2. Rendere il server raggiungibile dai player

Sul PC Windows che stai usando esegui **`Avvia_Server_LAN_Windows.bat`**, non il normale `Avvia_Windows.bat`. Questo e un cambiamento importante: l'avvio precedente rimaneva in ascolto solo su `127.0.0.1`, inaccessibile agli altri dispositivi.

Il nuovo avvio ascolta su tutte le interfacce, porta **TCP 8787**. Usa solo una LAN privata fidata. Mantieni il PC acceso, impedisci la sospensione durante la prova e lascia aperto il processo del server.

Sul PC esegui `ipconfig` e leggi l'IPv4 della scheda realmente connessa alla rete dei player. Nell'esempio seguente `192.168.1.20` e un segnaposto, non il tuo IP rilevato:

```text
http://192.168.1.20:8787
```

Apri questo indirizzo da un secondo PC/tablet nella stessa rete. `localhost` su quel dispositivo indicherebbe il dispositivo stesso, non il server.

Se non risponde: controlla prima IP, server avviato in modalita LAN, VLAN e isolamento dei client Wi-Fi. Autorizza Python solo sulla rete privata fidata. Non disattivare il firewall e non aprire la porta sul router Internet.

Per un amministratore che deve creare una regola dedicata su Windows, questo comando limita la porta alla subnet locale e al profilo Privato; va eseguito solo sulla rete fidata corretta:

```powershell
New-NetFirewallRule -DisplayName "Carisma Display LAN" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787 -Profile Private -RemoteAddress LocalSubnet
```

La porta 8787 serve al player; l'eventuale firewall della sorgente NDI e un controllo separato. Per il primo collaudo evita Wi-Fi ospiti e VLAN distinte.

## 3. Prima prova concreta da un browser fisico

1. Apri la regia sul PC server e crea/seleziona uno schermo, per esempio **TV Foyer**.
2. Assegna **Orologio e data** e selezionalo anche come contenuto di riserva. Per i Chromecast parti con una quota cache prudente, per esempio 150 MB e file piccoli.
3. Nella barra laterale premi **Collega player fisici**. Se necessario inserisci la chiave amministratore locale, gia presente nel file `data/access.key`.
4. Seleziona TV Foyer e premi **Genera codice di abbinamento**: ricevi 8 cifre, valide 10 minuti e utilizzabili una volta sola.
5. Sull'altro PC apri:

```text
http://IP-DEL-SERVER:8787/connect.html
```

6. Inserisci le 8 cifre. Si apre il player a schermo intero grafico; usa il fullscreen del browser per eliminare le sue barre.
7. Cambia il contenuto dalla regia. La postazione deve riceverlo e risultare collegata in Diagnostica.

Questo e un player browser **reale collegato al server**, non una finestra che condivide solo la memoria della demo HTML. La reale accessibilita dalla tua LAN resta da verificare sul posto.

Un codice nuovo invalida i vecchi codici dello stesso schermo. Un nuovo abbinamento completato sostituisce il precedente dispositivo di quello schermo. Per due TV indipendenti crea due schermi diversi; non riusare la stessa identita.

## 4. Generare il player per i Chromecast G454V

Esegui **`Compila_Player_Android_Windows.bat`**. E uno script di sviluppo: prepara gli strumenti e compila l'APK sul tuo PC; non e un installer di un APK gia pronto.

Lo script cerca un JDK 17+ gia presente, anche quello incluso in Android Studio. Se manca e `winget` e disponibile, propone l'installazione di Microsoft OpenJDK 21 e richiede il tuo consenso. In alternativa installa tu un JDK 17+ e ripeti. Non occorre installare un'app NDI di terzi.

Se manca l'SDK, scarica i command-line tools ufficiali Google con checksum SHA-256 fissato nel sorgente. Mostra le licenze SDK: **leggi e accetta tu**, non vengono accettate automaticamente. Prepara Android API 35, Build Tools 35.0.0 e Platform Tools. Serve Internet per i download iniziali, non per il normale funzionamento del player.

La procedura usa `aapt2`, `javac`, `d8`, `zipalign`, `apksigner`. Alla fine, **soltanto se tutte le operazioni riescono**, produce:

```text
android-build/Carisma_Player_TV_v0.5-alpha.apk
android-build/SHA256.txt
```

La chiave di firma e generata **sul tuo PC** in `data/android-signing/`. Conservala privatamente con la password: serve per aggiornare la stessa app senza disinstallarla. Non e la chiave amministratore del server e non deve essere distribuita ai player.

Se lo script fallisce, conserva l'errore: non disattivare verifiche checksum o firme. La build nativa non e stata eseguita in questo ambiente, quindi potrebbero emergere errori da correggere prima dell'installazione.

## 5. Installare sul primo Chromecast

Non aggiornare o sbloccare il bootloader per questa procedura. Serve solo l'installazione di un'app tramite ADB autorizzata sul dispositivo.

Abilita le opzioni sviluppatore e il debug dal menu del Chromecast. La procedura di connessione dipende dalla versione Android/firmware:

- Se trovi **Debug wireless** con codice di associazione, usa l'opzione 2 dello script di installazione. La porta di associazione puo essere diversa da quella di connessione.
- Con ADB USB gia autorizzato usa l'opzione 1. Un Chromecast puo richiedere una configurazione USB/alimentazione adatta; non si presume che basti un qualunque cavo.
- Usa l'opzione 3 solo se il dispositivo ha gia un endpoint ADB di rete attivo. Non assumere che la porta 5555 sia sempre disponibile.

Esegui **`Installa_Player_Chromecast_Windows.bat`**. Lo script mostra i dispositivi e ti chiede di specificare quello corretto. Accetta l'eventuale richiesta di autorizzazione sul TV. Non tenta root, exploit, reset o modifiche del launcher.

Dopo l'installazione dovrebbe apparire **Carisma Player** fra le app del TV. Aprila e inserisci:

```text
Indirizzo server: http://IP-DEL-PC:8787
Codice: le 8 cifre appena generate nella regia
```

L'app accetta in questa versione IPv4 privati, non nomi DNS o IP pubblici. Non inserire l'IP del Chromecast nel campo server. Attendi la prima sincronizzazione. Il tasto Indietro del telecomando apre il menu con audio, diagnostica, ricarica e nuovo abbinamento. Dopo il collaudo disattiva il debug: il funzionamento del player non usa ADB.

**Limite esplicito:** l'avvio automatico dell'app dopo riaccensione del Chromecast NON e implementato in questa versione. La riapertura manuale dell'app e distinta dal ripristino del programma locale. Non vengono soppressi il tasto Home o il launcher di Google.

## 6. Funzioni previste dal player Android alpha

Il codice include l'interfaccia HTML/CSS/JS nell'app, invece di scaricarla all'accensione. Il server fornisce solo programma, media e segmenti video. Il contenuto incluso viene servito a WebView tramite un'origine HTTPS locale intercettata, senza URL `file://`, accesso universale ai file o download di script dalla rete.

Le schermate, l'orologio, le playlist e i video gia sincronizzati usano lo stesso motore della regia. I dati vengono salvati in IndexedDB del WebView. L'attivazione di un programma nuovo avviene dopo la preparazione dei file richiesti.

Il sorgente gestisce la ricezione NDI **tramite il gateway centrale**, non decodifica NDI sul Chromecast:

```text
Sorgente NDI -> server Carisma + FFmpeg -> segmenti H.264/AAC -> Carisma Player
```

Nessun account Google o servizio Google Play e chiamato dal nostro codice. Il sistema Google TV sottostante non e stato rimosso: non si promette che tutto il sistema operativo smetta di comunicare con Google.

La compatibilita del WebView, i codec, il telecomando, la memoria, le temperature e la ripresa dopo interruzione dell'alimentazione vanno misurati sul G454V. Il semplice mantenimento dello schermo acceso nell'Activity non garantisce il comportamento della TV, CEC o un watchdog industriale.

## 7. Matrice di autonomia: cosa collaudare davvero

| Situazione | Comportamento previsto | Stato del collaudo |
|---|---|---|
| Internet assente, LAN presente | Programma e gateway locali | Nessuna dipendenza Internet nel codice; verifica sul posto |
| Regia non raggiungibile, player aperto | Ultimo programma e orologio continuano | Verificato in fixture con trasporto interrotto |
| Live interrotto | Contenuto locale di riserva, poi riconnessione | Verificato con FFmpeg reale e trasporto di test |
| Riapertura app senza LAN | Interfaccia inclusa + snapshot salvato | Logica provata con snapshot iniettato; persistenza Android NON verificata |
| Riaccensione Chromecast | Serve aprire Carisma Player | Avvio automatico NON implementato |
| Browser HTTP LAN chiuso e riaperto offline | Non garantito | Non confonderlo con la shell Android |

Non rimuovere la rete finche il player non segnala **Cache pronta**. La prima sincronizzazione non puo avvenire senza server. Una diretta richiede sempre LAN, sorgente e gateway.

## 8. Sicurezza del collaudo

Le credenziali del player sono diverse da quelle amministratore e vengono memorizzate come hash sul server. Ogni player riceve solo il suo schermo e i contenuti necessari. Non puo modificare palinsesti, elencare tutte le sorgenti, avviare ingressi non assegnati o fermare gli encoder degli altri.

Le autorizzazioni vengono controllate anche per file e segmenti live. La revoca non cancella contenuti gia scaricati: un dispositivo offline non puo ricevere un ordine di cancellazione.

Questa versione usa normalmente **HTTP non cifrato nella LAN fidata**. Non esporla su Internet o reti ospiti. Non e una soluzione multi-tenant o una piattaforma sottoposta ad audit di sicurezza.

## 9. Ordine consigliato per il collaudo sul posto

Esegui prima: secondo browser in LAN, orologio, cambio contenuto. Poi: un solo Chromecast, prima orologio/immagine, quindi video locale. Solo dopo: test video del server e una sorgente NDI vera a 360p/15 fps. Verifica separatamente audio e latenza.

Infine: disconnessione LAN, ripristino, riapertura app offline dopo sincronizzazione e riavvio elettrico. Registra CPU/temperatura del server e stabilita per una durata adeguata prima di moltiplicare i player. Il tuo trasmettitore NDI e i dispositivi fisici non sono stati raggiunti da questo ambiente.

## Fonti tecniche ufficiali consultate

```text
https://developer.android.com/training/tv/get-started/create
https://developer.android.com/develop/ui/views/layout/webapps/load-local-content
https://developer.android.com/tools/adb
https://developer.android.com/tools/sdkmanager
https://developer.android.com/studio
https://learn.microsoft.com/en-us/windows/dev-environment/java
https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule
```

Leggi anche `QA_PLAYER_FISICI_v0.5.md`: distingue i test reali delle API e di FFmpeg dalle fixture browser e da cio che non e stato eseguito.
