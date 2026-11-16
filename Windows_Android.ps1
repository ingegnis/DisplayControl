[CmdletBinding()]
param([ValidateSet('Build','Install')][string]$Action='Build')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
  if($Action -eq 'Build') {
    $python=$null
    $saved=Join-Path $PSScriptRoot '.setup\python-path.txt'
    if(Test-Path -LiteralPath $saved){$python=([IO.File]::ReadAllText($saved)).Trim()}
    if(-not $python -or -not (Test-Path -LiteralPath $python)){
      $cmd=Get-Command python.exe -ErrorAction SilentlyContinue
      if($cmd){$python=$cmd.Source}
    }
    if(-not $python){throw 'Prima esegui Verifica_NDI_Windows.bat per predisporre Python.'}
    & $python (Join-Path $PSScriptRoot 'build_android.py') --install-sdk
    exit $LASTEXITCODE
  }
  $sdkfile=Join-Path $PSScriptRoot '.setup\android-sdk-path.txt'
  $adb=$null
  if(Test-Path $sdkfile){$sdk=([IO.File]::ReadAllText($sdkfile)).Trim();$adb=Join-Path $sdk 'platform-tools\adb.exe'}
  if(-not $adb -or -not (Test-Path -LiteralPath $adb)){
    $cmd=Get-Command adb.exe -ErrorAction SilentlyContinue
    if($cmd){$adb=$cmd.Source}
  }
  if(-not $adb){throw 'ADB non trovato. Compila prima l app o installa Android SDK Platform Tools.'}
  $apk=Join-Path $PSScriptRoot 'android-build\Carisma_Player_TV_v0.5-alpha.apk'
  if(-not(Test-Path -LiteralPath $apk)){throw 'APK non presente. Esegui prima Compila_Player_Android_Windows.bat.'}
  Write-Host 'Collega solo il Chromecast che vuoi installare. Questo script non modifica firmware o launcher.'
  Write-Host '1 = ADB gia collegato via USB/rete; 2 = debug wireless con codice; 3 = connessione IP:porta gia abilitata'
  $mode=Read-Host 'Modalita'
  if($mode -eq '2'){
    $endpoint=Read-Host 'IP:porta di ABBINAMENTO mostrati sul Chromecast'
    if($endpoint -notmatch '^\d{1,3}(\.\d{1,3}){3}:\d{1,5}$'){throw 'Formato IP:porta non valido'}
    & $adb pair $endpoint
    if($LASTEXITCODE -ne 0){throw 'Abbinamento ADB non riuscito'}
  }
  if($mode -eq '2' -or $mode -eq '3'){
    $endpoint=Read-Host 'IP:porta di CONNESSIONE (puo differire dalla porta di abbinamento)'
    if($endpoint -notmatch '^\d{1,3}(\.\d{1,3}){3}:\d{1,5}$'){throw 'Formato IP:porta non valido'}
    & $adb connect $endpoint
  }
  & $adb devices -l
  $serial=Read-Host 'Copia esattamente il seriale/IP:porta del dispositivo autorizzato dalla lista'
  if($serial -notmatch '^[A-Za-z0-9._:-]+$'){throw 'Seriale non valido'}
  $state=(& $adb -s $serial get-state 2>&1 | Out-String).Trim()
  if($LASTEXITCODE -ne 0 -or $state -ne 'device'){throw 'Dispositivo non autorizzato: accetta la richiesta sul TV, poi ripeti.'}
  & $adb -s $serial install -r $apk
  if($LASTEXITCODE -ne 0){throw 'Installazione non riuscita. Non e stata dichiarata completata.'}
  & $adb -s $serial shell am start -n it.carisma.player/.MainActivity
  if($LASTEXITCODE -ne 0){throw 'APK installato ma avvio non confermato. Apri Carisma Player dal menu app del TV.'}
  Write-Host 'Comando di avvio inviato. Verifica lo schermo del TV. Disattiva il debug dopo il collaudo.'
} catch {Write-Host ('ERRORE: '+$_.Exception.Message) -ForegroundColor Red;exit 1}
