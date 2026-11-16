> Rapporto storico; non descrive il collaudo corrente. Vedi TEST_REPORT.md.

# QA Carisma Prompt v0.8-alpha — AKP03E

## Verificato in questo ambiente
- packet framing HID 1025 byte, BAT/image chunk e parser dei codici evento AKP03E;
- mapping 6 LCD, 3 encoder e 3 tasti laterali con transport simulato;
- pairing controller monouso e token dedicato;
- token controller non accetta API amministrative;
- allow-list dei comandi controller;
- TAKE PRIMARY/BACKUP e mapping OSC;
- heartbeat controller visibile nella regia;
- sintassi Python e JavaScript della pagina Prompt;
- regressione server/player fisici e monitor.

Test dedicati: 8 test AKP03E/controller. Test Prompt + controller: 16 superati. Regressione monitor: 18 superati. Regressione server/player fisici eseguita separatamente: tutti i test eseguiti sono passati; il modulo monitor richiede `PYTHONPATH=.:tests` quando lanciato singolarmente.

## NON verificato qui
- apertura di un AKP03E fisico VID:PID 0300:3002;
- orientamento effettivo delle icone sul singolo firmware dell'utente;
- reconnect USB reale dopo scollegamento;
- latenza percepita encoder → server → player sulla LAN del teatro;
- doppio Core HA reale e takeover del VIP;
- commutazione HDMI fisica.

Prima dello show eseguire `Test_Controller_AKP03E_Windows.bat` e verificare ogni controllo. Il comando TAKE della v0.8 e logico, non un commutatore HDMI.
