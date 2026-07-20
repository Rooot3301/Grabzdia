# Self-signed Authenticode signing for MediaGrab (name: Root3301).
#
# Signs the files passed as arguments with a self-signed code-signing
# certificate (created on first use, stored in the current user's store).
#
# NOTE: a self-signed certificate is NOT trusted by a public authority, so
# Windows SmartScreen will still show "unknown publisher". The signature proves
# integrity and carries the "Root3301" identity, but only removes the warning
# for users who explicitly trust the certificate. A commercial code-signing
# certificate is required to remove the warning for everyone.

param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Files)
$ErrorActionPreference = "Stop"

$Subject = "CN=Root3301"
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $Subject -and ($_.EnhancedKeyUsageList.FriendlyName -contains "Code Signing") } |
    Select-Object -First 1

if (-not $cert) {
    Write-Host "Creation d'un certificat auto-signe '$Subject'..."
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $Subject `
        -CertStoreLocation Cert:\CurrentUser\My -KeyUsage DigitalSignature `
        -FriendlyName "Root3301 Code Signing" -NotAfter (Get-Date).AddYears(5)
}

function Invoke-Sign([string]$Path) {
    try {
        return Set-AuthenticodeSignature -FilePath $Path -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
    }
    catch {
        Write-Warning "Horodatage indisponible, signature sans timestamp: $($_.Exception.Message)"
        return Set-AuthenticodeSignature -FilePath $Path -Certificate $cert -HashAlgorithm SHA256
    }
}

foreach ($file in $Files) {
    if (-not (Test-Path $file)) { throw "Fichier introuvable: $file" }
    $result = Invoke-Sign $file
    # 'Valid' when the cert is trusted; 'UnknownError' (untrusted root) still means
    # the signature was applied — that is expected for a self-signed certificate.
    Write-Host "Signature [$($result.Status)] : $file"
}
