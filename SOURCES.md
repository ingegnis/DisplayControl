# Riferimenti tecnici della v0.4

Consultati per questa implementazione. Non sono dipendenze caricate a runtime.

1. NDI Receive SDK e frame synchronization: API, ownership dei frame, riconnessione,
   ricampionamento audio, formati di ricezione.
   https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-recv
2. NDI Find SDK: nomi sorgenti, mDNS, extra IP e Avahi.
   https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-find
3. NDI frame types: descrittori, stride e timestamp.
   https://docs.ndi.video/all/developing-with-ndi/sdk/frame-types
4. NDI dynamic loading: runtime distribuito separatamente e percorsi.
   https://docs.ndi.video/all/developing-with-ndi/sdk/dynamic-loading-of-ndi-libraries
5. NDI platform considerations: dipendenze Avahi su Linux.
   https://docs.ndi.video/all/developing-with-ndi/sdk/platform-considerations
6. NDI SDK licensing e pagina prodotto: verificare i termini distribuiti col runtime.
   https://docs.ndi.video/all/developing-with-ndi/sdk/licensing
   https://ndi.video/for-developers/ndi-sdk/
7. NDI H.264 support: limitazioni/condizioni piattaforma da verificare, non promettere
   la decodifica HX su Linux in base alla sola discovery.
   https://docs.ndi.video/all/developing-with-ndi/advanced-sdk/using-h.264-h.265-and-aac-codecs/h.264-support
8. FFmpeg formats: muxer HLS, fMP4, segmenti indipendenti, finestra e rimozione.
   https://ffmpeg.org/ffmpeg-formats.html#hls-2
9. MDN MediaSource: buffer browser e verifica MIME.
   https://developer.mozilla.org/en-US/docs/Web/API/MediaSource

Non viene incorporato codice dei tutorial ne un runtime NDI da repository di terzi.
Il binding ctypes usa definizioni interoperabili dell'ABI; non include gli header
proprietari. WebRTC/aiortc sono stati valutati ma NON fanno parte di questa release.


## Patch setup Windows 0.4.1

- Build FFmpeg e checksum: https://www.gyan.dev/ffmpeg/builds/
- Distributore Windows indicato da FFmpeg: https://ffmpeg.org/download.html
- Python bootstrap e hash: https://www.python.org/downloads/release/python-31410/
- Runtime URL e ricerca DLL: https://docs.ndi.video/all/developing-with-ndi/sdk/dynamic-loading-of-ndi-libraries
- Condizioni installer NDI: https://docs.ndi.video/all/developing-with-ndi/sdk/software-distribution

Consultazione: 2026-10-29. Nessun binario di questi progetti incluso nel pacchetto.

## AJAZZ AKP03E / Carisma Prompt v0.8
- Protocol reference: https://github.com/Aiacos/ajazz-control-center/blob/develop/docs/protocols/streamdeck/akp03.md
- Hardware-tested Python reference: https://github.com/tomekceszke/ajazz-akp03e (MIT; consulted for protocol cross-check, not bundled as runtime)
- Ajazz SDK reference: https://github.com/mishamyrt/ajazz-sdk
- hidapi Python distribution: https://pypi.org/project/hidapi/
