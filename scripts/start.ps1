param(
    [string]$Model = 'qwen3.5:9b'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$TempRoot = Join-Path $ProjectRoot '.tmp'

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Independent D-drive environment not found. Run .\scripts\setup.ps1 first.'
}

Set-Location $ProjectRoot
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
if (-not $env:OLLAMA_MODELS -and (Test-Path -LiteralPath 'D:\Agent\Ollama\models')) {
    $env:OLLAMA_MODELS = 'D:\Agent\Ollama\models'
}
$env:PYTHONNOUSERSITE = '1'
$env:FOCUS_MODEL = $Model
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    Write-Host "Ollama online. Preferred model: $Model" -ForegroundColor Green
} catch {
    Write-Warning 'Ollama is offline. Goal planning will use local recommendations; monitoring and reminders still work.'
}

Write-Host "Python: $Python"
Write-Host 'Starting modern local Focus...'
& $Python -s -m focus_agent.web_app
