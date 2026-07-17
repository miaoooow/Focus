param(
    [string]$Version = '3.3.0',
    [bool]$IncludeLocalMusic = $false,
    [switch]$SkipWindowsInstaller
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$StageRoot = Join-Path $ProjectRoot '.tmp\public-editions'
$BrowserStage = Join-Path $StageRoot 'FocusBuddy-Browser-Extension'
$WebStage = Join-Path $StageRoot 'FocusBuddy-Web'
$BrowserZip = Join-Path $ReleaseRoot 'FocusBuddy-Browser-Extension.zip'
$WebZip = Join-Path $ReleaseRoot 'FocusBuddy-Web.zip'
$WindowsInstaller = Join-Path $ReleaseRoot 'FocusBuddy-Windows-Setup.exe'
$ChecksumFile = Join-Path $ReleaseRoot 'SHA256.txt'

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

$BrowserFiles = @('manifest.json','background.js','popup.html','popup.css','popup.js')
foreach ($name in $BrowserFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "browser_extension_standalone\$name") `
        -Destination (Join-Path $BrowserStage $name)
}

$WebFiles = @('index.html','styles.css','app.js','manifest.webmanifest','sw.js')
foreach ($name in $WebFiles) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "web_standalone\$name") `
        -Destination (Join-Path $WebStage $name)
}
$WebMedia = Join-Path $WebStage 'media'
New-Item -ItemType Directory -Path $WebMedia -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'pictures') -Filter '*.png' -File |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $WebMedia $_.Name)
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
