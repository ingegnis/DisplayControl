# Carisma v0.5.1-alpha - riduzione del ritardo live

## Perche il video aveva alcuni secondi di ritardo

Il codice della v0.5 creava segmenti H.264/AAC da circa 1 secondo. Il player,
all'avvio, si posizionava due secondi prima dell'ultimo dato disponibile
(`end - 2`) e verificava nuovi segmenti ogni 500 ms. Non recuperava
l'arretrato finche la coda non superava 5 secondi.

Queste attese sono nel nostro percorso NDI -> FFmpeg -> browser. Non dimostrano
un difetto della tua LAN o della sorgente NDI. Il ritardo effettivo comprende
anche trasmettitore, ricevitore NDI, conversione, trasporto e schermo.

## Installazione sulla tua v0.5-alpha

1. Chiudi il server Carisma e fai una copia della cartella esistente.
2. Estrai `Carisma_Aggiornamento_Latenza_v0.5.1.zip` in una cartella temporanea.
3. Copia TUTTO il contenuto estratto nella cartella di `server.py`, accettando
   la sostituzione dei file e unendo le sottocartelle. Non avviare dallo ZIP.
4. Riavvia `Avvia_Server_LAN_Windows.bat`.
5. Nella regia e su ogni PC player ricarica la pagina (Ctrl+F5 su Windows).
   Non cancellare dati del browser, cache dei contenuti o abbinamenti.
6. In `Ingressi NDI` verifica `Modalita live: Reattiva / LAN` e
   `Buffer obiettivo player: 0.75 s`. La UI mostra v0.5.1-alpha.
7. Nel player premi `Mostra controlli`, poi `Torna alla diretta` per forzare
   il recupero rispetto all'ultimo video gia disponibile dal server.

La patch non contiene `data/`, `bin/`, `.setup/`, `Config_Locale.bat`, chiavi o
librerie NDI. Non cambia i tuoi schermi, abbinamenti, palinsesti o contenuti.
Non installa dipendenze nuove, non cambia firewall e non richiede Internet.
La patch va applicata alla v0.5, non da sola alla v0.4.

Il progetto completo e disponibile in un archivio separato. Per usarlo come
sostituto, a server fermo trasferisci dalla vecchia cartella `data/`, `bin/`,
`.setup/` e `Config_Locale.bat` se presenti. Mantieni privata la copia dei dati.

## Cosa cambia

| Parametro | v0.5 / modalita Stabile | v0.5.1 Reattiva (default) |
|---|---:|---:|
| Obiettivo durata segmenti | 1 s | 0.5 s |
| Durata nominale a 15 fps | 1 s | 0.533 s (8 fotogrammi) |
| Durata nominale a 25 fps | 1 s | 0.520 s (13 fotogrammi) |
| Buffer obiettivo del player | 2 s | 0.75 s |
| Intervallo controllo segmenti | 500 ms | 100 ms |
| Recupero arretrato nel buffer | oltre 5 s | oltre 1.8 s |

I keyframe vengono allineati ai nuovi segmenti. Il client ignora i segmenti
ormai troppo vecchi dopo un'interruzione invece di scaricare tutto l'arretrato.
Il pulsante `Torna alla diretta` recupera il video gia disponibile; NON elimina
il ritardo a monte della sorgente o dell'encoder.

La scritta `coda player` indica solo `fine buffer - posizione di riproduzione`.
NON e una misura della latenza NDI o del ritardo totale sorgente-schermo.
La soglia 1.8 s e una regola di recupero, NON un limite massimo garantito alla latenza.
Rimangono profilo Leggero 360p/15 fps e Standard 720p/25 fps.

## Modalita Stabile, per confronto o rete irregolare

La modalita Reattiva riduce il margine contro interruzioni e comporta richieste
HTTP piu frequenti. Se compaiono scatti, usa Stabile per confrontare.

Su Windows aggiungi questa riga al tuo `Config_Locale.bat` (senza sostituirne
le righe esistenti), poi riavvia il server e ricarica i player:

```bat
set "CARISMA_LIVE_MODE=stable"
```

Per riattivare la modalita veloce cambia soltanto `stable` in `responsive`.
Su Linux o da linea di comando puoi scegliere esplicitamente:

```sh
python3 server.py --host 0.0.0.0 --port 8787 --live-mode responsive
# oppure --live-mode stable
```

Non aumentare contemporaneamente risoluzione, numero di sorgenti e numero di
player durante la prima prova. Mantieni il profilo che gia funziona, confronta
il ritardo, poi valuta il carico.

## Come misurare il ritardo sul posto

Mostra un cronometro sulla sorgente realmente inviata in NDI. Affianca il suo
monitor a quello del player e riprendili nello stesso video: nello stesso
fotogramma sottrai i due valori. Cosi il confronto non dipende da due orologi
di sistema diversamente sincronizzati. Ripeti piu volte dopo l'avvio e dopo
qualche minuto. Annota se il ritardo resta costante, aumenta o appare a scatti.

Confronta inoltre il generatore `Test locale / NON NDI` con la sorgente reale.
Il generatore prova la conversione e il percorso browser ma non il trasmettitore
NDI. Se solo la sorgente reale resta molto indietro, indaga anche quel tratto.
Sul server verifica il carico CPU e i singoli core durante la prova; non si
puo dedurre un sovraccarico dal solo ritardo segnalato.

## Limiti

E ancora distribuzione di segmenti fMP4, NON NDI nativo nel browser e NON WebRTC.
Non promette 100 ms, sincronizzazione al fotogramma o labiale da monitor palco.
Il server resta locale e il fallback offline resta invariato.

Sono inclusi anche i sorgenti aggiornati della shell Android per coerenza, ma
nessun APK nuovo o prova Chromecast: questa patch e collaudata come codice
server/player browser nei limiti del rapporto. Un'app Android gia installata
non si aggiorna ricaricando la pagina: richiede ricompilazione/installazione.

Leggi `QA_LATENZA_v0.5.1.md` per i risultati misurati e i limiti dell'ambiente.
