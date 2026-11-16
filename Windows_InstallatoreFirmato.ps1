# Native Windows helper. No silent NDI licence acceptance, no certificate bypass.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallerPath,
    [Parameter(Mandatory=$true)][ValidateSet('NDI','Python')][string]$Product
)
$ErrorActionPreference = 'Stop'
try {
    $file = (Resolve-Path -LiteralPath $InstallerPath).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $file
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate) {
        throw "Firma digitale non valida: $($signature.Status). Il file NON viene eseguito."
    }
    $publisher = $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    if ($Product -eq 'Python') {
        if ($publisher -ne 'Python Software Foundation') { throw "Editore Python inatteso: $publisher" }
    } else {
        if ($publisher -notmatch '^(NewTek(,? Inc\.?)?|Vizrt( NDI)?( AB| AS| Group|,? Inc\.?)?|NDI( AB| AS|,? Inc\.?| LLC)?)$') {
            throw "Editore NDI inatteso: $publisher. Verifica necessaria; installazione bloccata."
        }
    }
    Write-Host "Firma valida. Editore: $publisher"
    if ($Product -eq 'Python') {
        # Per-user installation. Do not change global aliases, PATH or launchers.
        $arguments = @('/passive', '/norestart', 'InstallAllUsers=0', 'PrependPath=0',
            'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'Shortcuts=0')
        $process = Start-Process -FilePath $file -ArgumentList $arguments -Wait -PassThru
    } else {
        Write-Host 'Completa la procedura ufficiale NDI e accetta personalmente la licenza.'
        # Leave the installer UI visible; elevation is approved through Windows UAC.
        $process = Start-Process -FilePath $file -Verb RunAs -Wait -PassThru
    }
    if ($process.ExitCode -eq 3010) { Write-Host 'Riavvio richiesto dal fornitore, NON eseguito automaticamente.' }
    exit $process.ExitCode
} catch {
    Write-Host ("ERRORE INSTALLER: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
