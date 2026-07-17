param(
    [string]$Version = '3.3.0',
    [switch]$IncludeLocalMusic,
    [switch]$PortableZip,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DistRoot = Join-Path $ProjectRoot 'dist'
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$PortableRoot = Join-Path $DistRoot 'FocusBuddyAI'
$TempRoot = Join-Path $ProjectRoot '.tmp'

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'D-drive build environment not found. Run .\scripts\setup.ps1 first.'
}

Set-Location $ProjectRoot
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:PYINSTALLER_CONFIG_DIR = Join-Path $TempRoot 'pyinstaller-cache'
$env:PYTHONNOUSERSITE = '1'
$BundleMusic = if ($PSBoundParameters.ContainsKey('IncludeLocalMusic')) {
    [bool]$IncludeLocalMusic
} else {
    $false
}
$env:FOCUS_BUDDY_BUNDLE_MUSIC = if ($BundleMusic) { '1' } else { '0' }

& $Python -s -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is missing. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt'
}

& $Python -s -m PyInstaller --noconfirm --clean .\FocusBuddy.spec
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

$ExtensionTarget = Join-Path $PortableRoot 'browser_extension'
if (Test-Path -LiteralPath $ExtensionTarget) {
    Remove-Item -LiteralPath $ExtensionTarget -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'browser_extension') -Destination $ExtensionTarget -Recurse
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'README.md') -Destination (Join-Path $PortableRoot 'README.md') -Force

New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
$MusicSuffix = if ($BundleMusic) { '-with-local-music' } else { '' }
$ZipPath = Join-Path $ReleaseRoot "FocusBuddyAI-Portable-$Version$MusicSuffix.zip"
if ($PortableZip) {
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -LiteralPath $PortableRoot -DestinationPath $ZipPath -CompressionLevel Optimal
}

$InnoCandidates = @(
    @(
        $env:FOCUS_BUDDY_ISCC,
        'D:\Agent\tools\Inno Setup 6\ISCC.exe',
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
)

if (-not $SkipInstaller -and $InnoCandidates.Count -gt 0) {
    $InnoCompiler = $InnoCandidates[0]
    & $InnoCompiler "/DMyAppVersion=$Version" '.\installer\FocusBuddy.iss'
    if ($LASTEXITCODE -ne 0) {
        throw 'Inno Setup build failed.'
    }
} elseif (-not $SkipInstaller) {
    Write-Warning 'Inno Setup compiler was not found; portable ZIP was built successfully.'
}

Write-Host "Portable app: $PortableRoot" -ForegroundColor Green
if ($PortableZip) {
    Write-Host "Portable ZIP: $ZipPath" -ForegroundColor Green
}
