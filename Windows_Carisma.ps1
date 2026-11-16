# Bootstrap for Windows PowerShell 5.1+. Only process-level execution policy is used.
[CmdletBinding()]
param([ValidateSet('Repair','Check','Start','StartLan')][string]$Action = 'Repair')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = $PSScriptRoot
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
# Discovery must not trigger automatic downloads through a Python launcher.
$env:PYTHON_MANAGER_AUTOMATIC_INSTALL = 'false'
Remove-Item Env:PYLAUNCHER_ALLOW_INSTALL -ErrorAction SilentlyContinue
Set-Location -LiteralPath $Root
$PythonVersion = '3.14.10'
$PythonUrl = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe'
$PythonHash = '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965'
$Probe = 'import sys,struct,sqlite3,ssl,json,ctypes; print(json.dumps(dict(executable=sys.executable, version=list(sys.version_info[:3]), bits=struct.calcsize("P")*8)))'

function Quote-NativeArgument([string]$Value) {
    # Windows CommandLineToArgvW quoting, including embedded quotes/backslashes.
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Test-PythonCandidate([string]$File, [string[]]$Prefix = @()) {
    if (-not $File -or $File -match '\\WindowsApps\\') { return $null }
    $process = $null
    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $File
        $arguments = @($Prefix) + @('-c', $Probe)
        $info.Arguments = (($arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' ')
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.StandardOutputEncoding = $Utf8
        $info.StandardErrorEncoding = $Utf8
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $info
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) { $process.Kill(); return $null }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { return $null }
        $value = $stdout.Result.Trim() | ConvertFrom-Json
        if ($value.bits -eq 64 -and $value.version[0] -eq 3 -and $value.version[1] -ge 9 -and
            (Test-Path -LiteralPath $value.executable -PathType Leaf)) {
            return [string]$value.executable
        }
    } catch { return $null }
    finally { if ($null -ne $process) { $process.Dispose() } }
    return $null
}

function Find-Python {
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if ($env:CARISMA_PYTHON) { $candidates.Add($env:CARISMA_PYTHON) }
    $saved = Join-Path $Root '.setup\python-path.txt'
    if (Test-Path -LiteralPath $saved) {
        $candidates.Add(([System.IO.File]::ReadAllText($saved, $Utf8)).Trim())
    }
    foreach ($name in @('python.exe','python3.exe')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { $candidates.Add($command.Source) }
    }
    # PEP 514 registry entries, without assuming that Python is on PATH.
    foreach ($registry in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore',
                           'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        foreach ($key in @(Get-ChildItem -Path $registry -ErrorAction SilentlyContinue)) {
            $item = Get-Item -LiteralPath ($key.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
            if ($item) {
                $exe = [string]$item.GetValue('ExecutablePath', '')
                $directory = [string]$item.GetValue('', '')
                if ($exe) { $candidates.Add($exe) }
                elseif ($directory) { $candidates.Add((Join-Path $directory 'python.exe')) }
            }
        }
    }
    if ($env:LOCALAPPDATA) {
        foreach ($exe in @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe') -ErrorAction SilentlyContinue)) {
            $candidates.Add($exe.FullName)
        }
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $found = Test-PythonCandidate -File $candidate
            if ($found) { return $found }
        }
    }
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) {
        $found = Test-PythonCandidate -File $launcher.Source -Prefix @('-3')
        if ($found) { return $found }
    }
    return $null
}

function Install-Python {
    $folder = Join-Path $Root '.setup\downloads'
    [void](New-Item -ItemType Directory -Force -Path $folder)
    $installer = Join-Path $folder ("python-$PythonVersion-amd64.exe")
    $valid = $false
    if (Test-Path -LiteralPath $installer -PathType Leaf) {
        $valid = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -eq $PythonHash
    }
    if (-not $valid) {
        Write-Host "Python compatibile non trovato. Scarico Python $PythonVersion x64 da python.org."
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $partial = $installer + '.' + [guid]::NewGuid().ToString('N') + '.part'
        try {
            # No permanent TLS, security or proxy setting changes.
            Invoke-WebRequest -Uri $PythonUrl -OutFile $partial -UseBasicParsing -TimeoutSec 180
            if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $PythonHash) {
                throw 'SHA-256 Python non valido. Nessun installer viene eseguito.'
            }
            Move-Item -LiteralPath $partial -Destination $installer -Force
        } finally {
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        }
    }
    Write-Host 'Checksum Python OK. Installazione per il solo utente, senza cambiare PATH.'
    $helper = Join-Path $Root 'Windows_InstallatoreFirmato.ps1'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $helper -InstallerPath $installer -Product Python | Out-Host
    $code = $LASTEXITCODE
    if ($code -notin @(0,3010)) { throw "Installazione Python non completata (codice $code)." }
    $found = Find-Python
    if (-not $found) { throw 'Python non utilizzabile dopo installazione. Riavvia se richiesto e ripeti la verifica.' }
    return $found
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Questa installazione richiede Windows x64.' }
    $architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    if ($architecture -ne 'AMD64') { throw "Architettura $architecture non supportata dal setup Windows x64." }
    foreach ($required in @('setup_ndi.py','diagnose_ndi.py','Windows_InstallatoreFirmato.ps1','server.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $required))) {
            throw "File mancante: $required. Estrai tutto il pacchetto, non solo il file BAT."
        }
    }
    $python = Find-Python
    if (-not $python) {
        if ($Action -eq 'Check') { throw 'Python >= 3.9 a 64 bit non trovato. Usa Verifica_NDI_Windows.bat per installarlo.' }
        $python = Install-Python
    }
    Write-Host "Python selezionato: $python"
    if ($Action -ne 'Check') {
        $folder = Join-Path $Root '.setup'
        [void](New-Item -ItemType Directory -Force -Path $folder)
        [System.IO.File]::WriteAllText((Join-Path $folder 'python-path.txt'), $python, $Utf8)
    }
    $operation = switch ($Action) { 'Repair' { 'repair' } 'Check' { 'check' } 'Start' { 'launch' } 'StartLan' { 'launch-lan' } }
    & $python (Join-Path $Root 'setup_ndi.py') $operation
    exit $LASTEXITCODE
} catch {
    Write-Host ("ERRORE: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Non modificare le policy aziendali o il firewall per aggirare questo errore.'
    exit 1
}
