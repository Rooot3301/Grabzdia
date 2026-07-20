$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 1. Build the application (validates lint + tests, produces dist\MediaGrab).
& (Join-Path $ProjectRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { throw "Le build de l'application a échoué." }

# 2. Read the single source of truth for the version.
$VersionLine = Select-String -Path (Join-Path $ProjectRoot "app\version.py") -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $VersionLine) { throw "Version introuvable dans app\version.py." }
$Version = $VersionLine.Matches[0].Groups[1].Value
Write-Host "Version detectee: $Version"

# 3. Locate the Inno Setup compiler.
$Iscc = $null
$Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
foreach ($candidate in $Candidates) {
    if ($candidate -and (Test-Path $candidate)) { $Iscc = $candidate; break }
}
if (-not $Iscc) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $Iscc = $command.Source }
}
if (-not $Iscc) {
    throw "Inno Setup (ISCC.exe) est introuvable. Installez-le depuis https://jrsoftware.org/isdl.php puis relancez."
}

# 4. Compile the installer.
$Iss = Join-Path $ProjectRoot "installer\MediaGrab.iss"
& $Iscc "/DMyAppVersion=$Version" $Iss
if ($LASTEXITCODE -ne 0) { throw "La compilation de l'installateur a échoué." }

$Output = Join-Path $ProjectRoot "installer\Output\MediaGrab-Setup-$Version.exe"
if (-not (Test-Path $Output)) { throw "Installateur final introuvable: $Output" }

# Sign the installer (self-signed, best-effort).
try {
    & (Join-Path $ProjectRoot "installer\sign.ps1") $Output
}
catch {
    Write-Warning "Signature de l'installateur ignoree: $($_.Exception.Message)"
}

Write-Host "Installateur cree: $Output"
