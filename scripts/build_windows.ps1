param(
    [string]$Version = '4.1.0',
    [switch]$IncludeLocalMusic,
    [switch]$PortableZip,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DistRoot = Join-Path $ProjectRoot 'dist'
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$PortableRoot = Join-Path $DistRoot 'Focus'
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
$env:FOCUS_BUNDLE_MUSIC = if ($BundleMusic) { '1' } else { '0' }

& $Python -s -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is missing. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt'
}

& $Python -s -m PyInstaller --noconfirm --clean .\Focus.spec
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

$ExtensionTarget = Join-Path $PortableRoot 'browser_extension'
if (Test-Path -LiteralPath $ExtensionTarget) {
    Remove-Item -LiteralPath $ExtensionTarget -Recurse -Force
}
New-Item -ItemType Directory -Path $ExtensionTarget -Force | Out-Null
foreach ($name in @('manifest.json','background.js','bridge.js','popup.html','popup.css','popup.js')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "browser_extension_standalone\$name") `
        -Destination (Join-Path $ExtensionTarget $name)
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'web_standalone\index.html') `
    -Destination (Join-Path $ExtensionTarget 'focus.html')
foreach ($name in @('styles.css','app.js','manifest.webmanifest')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "web_standalone\$name") `
        -Destination (Join-Path $ExtensionTarget $name)
}
$ExtensionMedia = Join-Path $ExtensionTarget 'media'
New-Item -ItemType Directory -Path (Join-Path $ExtensionMedia 'sounds') -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'pictures') -Filter '*.png' -File |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $ExtensionMedia $_.Name) }
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'assets\soundscapes') -Filter '*.ogg' -File |
    ForEach-Object {
        $soundTarget = Join-Path (Join-Path $ExtensionMedia 'sounds') $_.Name
        Copy-Item -LiteralPath $_.FullName -Destination $soundTarget
    }
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'README.md') -Destination (Join-Path $PortableRoot 'README.md') -Force

New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
$MusicSuffix = if ($BundleMusic) { '-with-local-music' } else { '' }
$ZipPath = Join-Path $ReleaseRoot "Focus-Portable-$Version$MusicSuffix.zip"
if ($PortableZip) {
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -LiteralPath $PortableRoot -DestinationPath $ZipPath -CompressionLevel Optimal
}

$InnoCandidates = @(
    @(
        $env:FOCUS_ISCC,
        'D:\Agent\tools\Inno Setup 6\ISCC.exe',
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
)

if (-not $SkipInstaller -and $InnoCandidates.Count -gt 0) {
    $InnoCompiler = $InnoCandidates[0]
    & $InnoCompiler "/DMyAppVersion=$Version" '.\installer\Focus.iss'
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
