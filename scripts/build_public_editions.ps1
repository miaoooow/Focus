param(
    [string]$Version = '4.1.0',
    [bool]$IncludeLocalMusic = $false,
    [switch]$SkipWindowsInstaller
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$StageRoot = Join-Path $ProjectRoot '.tmp\public-editions'
$BrowserStage = Join-Path $StageRoot 'Focus-Browser-Extension'
$WebStage = Join-Path $StageRoot 'Focus-Web'
$BrowserZip = Join-Path $ReleaseRoot 'Focus-Browser-Extension.zip'
$WebZip = Join-Path $ReleaseRoot 'Focus-Web.zip'
$WindowsInstaller = Join-Path $ReleaseRoot 'Focus-Windows-Setup.exe'
$ChecksumFile = Join-Path $ReleaseRoot 'SHA256.txt'
$CloudConfig = Join-Path $ProjectRoot 'data\focus_cloud.json'

Set-Location $ProjectRoot
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
if (Test-Path -LiteralPath $StageRoot) {
    $resolved = (Resolve-Path -LiteralPath $StageRoot).Path
    $tempRoot = (Resolve-Path -LiteralPath (Join-Path $ProjectRoot '.tmp')).Path
    if (-not $resolved.StartsWith($tempRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "Unsafe staging path: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
New-Item -ItemType Directory -Path $BrowserStage,$WebStage -Force | Out-Null

if (-not $SkipWindowsInstaller) {
    & (Join-Path $PSScriptRoot 'build_windows.ps1') `
        -Version $Version `
        -IncludeLocalMusic:$IncludeLocalMusic
    if ($LASTEXITCODE -ne 0) {
        throw 'Windows installer build failed.'
    }
}

$BrowserFiles = @('manifest.json','background.js','bridge.js','popup.html','popup.css','popup.js')
foreach ($name in $BrowserFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "browser_extension_standalone\$name") `
        -Destination (Join-Path $BrowserStage $name)
}

# The released extension contains the same complete focus console as the
# no-install web edition. The popup is only a lightweight launcher/status view;
# the background service worker remains authoritative for cross-tab monitoring.
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'web_standalone\index.html') `
    -Destination (Join-Path $BrowserStage 'focus.html')
foreach ($name in @('styles.css','app.js','manifest.webmanifest')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "web_standalone\$name") `
        -Destination (Join-Path $BrowserStage $name)
}
$BrowserMedia = Join-Path $BrowserStage 'media'
New-Item -ItemType Directory -Path $BrowserMedia -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'pictures') -Filter '*.png' -File |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $BrowserMedia $_.Name)
    }
$BrowserSounds = Join-Path $BrowserMedia 'sounds'
New-Item -ItemType Directory -Path $BrowserSounds -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'assets\soundscapes') -Filter '*.ogg' -File |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $BrowserSounds $_.Name)
    }

$WebFiles = @('index.html','styles.css','app.js','manifest.webmanifest','sw.js')
foreach ($name in $WebFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "web_standalone\$name") `
        -Destination (Join-Path $WebStage $name)
}

# A deployed Focus Cloud URL is a publisher setting, never an end-user file.
# When configured, bake it into the offline web and extension consoles.
if (Test-Path -LiteralPath $CloudConfig) {
    $cloudUrl = [string]((Get-Content -LiteralPath $CloudConfig -Raw | ConvertFrom-Json).base_url)
    $cloudUrl = $cloudUrl.Trim().TrimEnd('/')
    if ($cloudUrl) {
        if (-not $cloudUrl.StartsWith('https://')) {
            throw 'Focus Cloud release URL must use HTTPS.'
        }
        $escapedCloudUrl = [Security.SecurityElement]::Escape($cloudUrl)
        foreach ($htmlPath in @(
            (Join-Path $BrowserStage 'focus.html'),
            (Join-Path $WebStage 'index.html')
        )) {
            $html = Get-Content -LiteralPath $htmlPath -Raw
            $html = $html.Replace(
                '<meta name="focus-cloud-url" content="" />',
                "<meta name=`"focus-cloud-url`" content=`"$escapedCloudUrl`" />"
            )
            Set-Content -LiteralPath $htmlPath -Value $html -Encoding utf8
        }
    }
}
$WebMedia = Join-Path $WebStage 'media'
New-Item -ItemType Directory -Path $WebMedia -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'pictures') -Filter '*.png' -File |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $WebMedia $_.Name)
    }
$WebSounds = Join-Path $WebMedia 'sounds'
New-Item -ItemType Directory -Path $WebSounds -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'assets\soundscapes') -Filter '*.ogg' -File |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $WebSounds $_.Name)
    }

foreach ($archive in @($BrowserZip,$WebZip)) {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}
Compress-Archive -Path (Join-Path $BrowserStage '*') -DestinationPath $BrowserZip -CompressionLevel Optimal
Compress-Archive -Path (Join-Path $WebStage '*') -DestinationPath $WebZip -CompressionLevel Optimal

$Artifacts = @($WindowsInstaller,$BrowserZip,$WebZip) |
    Where-Object { Test-Path -LiteralPath $_ }
if ($Artifacts.Count -lt 2) {
    throw 'Expected public artifacts were not produced.'
}
$ChecksumLines = foreach ($artifact in $Artifacts) {
    $hash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
    "$($hash.Hash)  $([IO.Path]::GetFileName($artifact))"
}
$ChecksumLines | Set-Content -LiteralPath $ChecksumFile -Encoding ascii

Write-Host 'Public release artifacts:' -ForegroundColor Green
Get-Item -LiteralPath @($Artifacts + $ChecksumFile) |
    Select-Object Name,Length,LastWriteTime |
    Format-Table -AutoSize
