> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# Verifica v0.2 - Orologio e data

## Controlli eseguiti

- Sintassi JavaScript verificata con Node.js per i file HTML generati.
- Sei test originali del server Python superati: autenticazione, heartbeat,
  payload invalido, revisioni concorrenti, persistenza al riavvio,
  caricamento/verifica hash/download dei contenuti.
- Controlli DOM e interazione eseguiti con Chromium/Playwright.

- Compact demo contains assignable local clocks; timezone Europe/Rome is applied.
- Clock advances with simulated player disconnection and browser network disabled.
- Disconnected clock keeps its previous programme; reconnect applies pending content.
- Previously received clock schedule activates without a connection.
- Simulated live source falls back to the local clock when LAN is absent.
- Compact UI and clock require zero network requests and produce no JavaScript errors.
- Mobile layout at 390px has no horizontal overflow.
- Full library supports clock creation, live theme preview, editing and local saving.
- Invalid timezone is rejected; hide-seconds setting is saved.
- Clock can be assigned from quick control and selected as live fallback.
- Clock is available as a playlist item.
- Existing projects are migrated once without changing screen assignments.
- Date and weekday roll over at local midnight, with 00-hour formatting.
- Reduced-motion preference disables decorative animation.
- Three clock themes render without JavaScript errors.

## Metodo e limiti

I test browser caricano il documento con `set_content`: la navigazione a URL e
file locali e bloccata dalle policy del browser di questa sessione. Nei test della
console completa, localStorage usa un sostituto in memoria e la modalita demo e
forzata nell'harness, senza modificare il codice distribuito. Non e una verifica
end-to-end di un'installazione reale e non verifica la persistenza IndexedDB.
La prova dell'orologio offline include la disabilitazione della rete nel contesto
browser. Il server e testato separatamente via HTTP locale dai test Python.
Nessuna prova e stata eseguita su Chromecast o NEXCOM. Il cold-start offline del
player rimane da collaudare sul dispositivo reale.

Sono state ispezionate le schermate a 1280x720, 1440px e 390px di larghezza.
Il rendering orologio utilizza HTML/CSS e l'ora di sistema; non usa NDI o video.
