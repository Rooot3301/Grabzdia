# Installe le certificat auto-signé Root3301 comme éditeur de confiance SUR CETTE
# MACHINE, afin que les binaires MediaGrab signés soient reconnus ici (supprime
# l'avertissement « éditeur inconnu » / SmartScreen sur ce PC).
#
# Ne concerne QUE la machine où on l'exécute — cela ne change rien pour les
# autres utilisateurs qui téléchargeraient MediaGrab. Nécessite les droits
# administrateur.
#
# Usage :  clic droit > « Exécuter avec PowerShell » (en admin), ou :
#          powershell -ExecutionPolicy Bypass -File installer\trust-cert.ps1

$ErrorActionPreference = "Stop"

# Élévation automatique si nécessaire.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Droits administrateur requis — relance en tant qu'administrateur..."
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    return
}

$Subject = "CN=Root3301"
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $Subject -and $_.HasPrivateKey } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1
if (-not $cert) {
    throw "Certificat '$Subject' introuvable. Lancez d'abord une signature (build.ps1 ou installer\sign.ps1)."
}

$temp = Join-Path $env:TEMP "Root3301.cer"
Export-Certificate -Cert $cert -FilePath $temp -Force | Out-Null
try {
    Import-Certificate -FilePath $temp -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
    Import-Certificate -FilePath $temp -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
}
finally {
    Remove-Item $temp -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "OK : Root3301 est maintenant un editeur de confiance sur cette machine."
Write-Host "Si l'installateur a ete telecharge depuis Internet, debloquez-le une fois :"
Write-Host "    Clic droit > Proprietes > cocher 'Debloquer'   (ou)"
Write-Host "    Unblock-File 'C:\chemin\MediaGrab-Setup-1.0.1.exe'"
