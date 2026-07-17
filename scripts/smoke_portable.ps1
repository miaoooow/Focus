param(
    [string]$Executable = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\FocusBuddyAI\FocusBuddyAI.exe'),
    [switch]$RequireAI,
    [switch]$RequireFallback
)

$ErrorActionPreference = 'Stop'
if ($RequireAI -and $RequireFallback) {
    throw 'RequireAI and RequireFallback cannot be used together.'
}
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DataRoot = Join-Path $ProjectRoot '.runtime\portable-smoke'
$Process = $null

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Portable executable not found: $Executable"
}
if (Test-Path -LiteralPath $DataRoot) {
    $resolved = (Resolve-Path -LiteralPath $DataRoot).Path
    $runtime = (Resolve-Path -LiteralPath (Join-Path $ProjectRoot '.runtime')).Path
    if (-not $resolved.StartsWith($runtime + [IO.Path]::DirectorySeparatorChar)) {
        throw 'Unsafe smoke-test data path'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

try {
    $env:FOCUS_BUDDY_NO_BROWSER = '1'
    $env:FOCUS_AGENT_DATA_DIR = $DataRoot
    if ($RequireFallback) {
        $env:FOCUS_BUDDY_OLLAMA_URL = 'http://127.0.0.1:65534'
    }
    $Process = Start-Process -FilePath $Executable -WindowStyle Hidden -PassThru

    $BaseUrl = $null
    $Health = $null
    for ($attempt = 0; $attempt -lt 80 -and -not $BaseUrl; $attempt++) {
        foreach ($port in 8765..8775) {
            $probe = [Net.Sockets.TcpClient]::new()
            try {
                $connect = $probe.ConnectAsync('127.0.0.1', $port)
                if (-not $connect.Wait(100) -or -not $probe.Connected) {
                    continue
                }
                $candidate = "http://127.0.0.1:$port"
                $health = Invoke-RestMethod -Uri "$candidate/api/health" -TimeoutSec 1
                if (
                    $health.ok -and
                    $health.data.version -eq 8 -and
                    $health.data.service -eq 'focus-buddy-ai'
                ) {
                    $BaseUrl = $candidate
                    $Health = $health
                    break
                }
            } catch {
            } finally {
                $probe.Dispose()
            }
        }
        if (-not $BaseUrl) {
            Start-Sleep -Milliseconds 125
        }
    }
    if (-not $BaseUrl) {
        throw 'Packaged app did not expose the Focus Buddy AI local API'
    }

    $planBody = @{
        goal = 'Finish Python coursework and run tests in 45 minutes'
        use_ai = $false
    } |
        ConvertTo-Json -Compress
    $plan = Invoke-RestMethod -Uri "$BaseUrl/api/plan" -Method Post `
        -ContentType 'application/json; charset=utf-8' -Body $planBody
    $values = @($plan.data.config.allowed_targets | ForEach-Object { $_.value })
    foreach ($expected in @('Code.exe', 'WindowsTerminal.exe', 'explorer.exe')) {
        if ($expected -notin $values) {
            throw "Packaged goal planner missed $expected"
        }
    }

    $aiBody = @{
        goal = 'Edit an interview recording into a podcast in 35 minutes'
        use_ai = $true
    } | ConvertTo-Json -Compress
    $aiPlan = Invoke-RestMethod -Uri "$BaseUrl/api/plan" -Method Post `
        -ContentType 'application/json; charset=utf-8' -Body $aiBody -TimeoutSec 100
    if ($RequireAI -and -not $aiPlan.data.ai_used) {
        throw "Packaged AI planner fell back: $($aiPlan.data.fallback_reason)"
    }
    if ($RequireFallback) {
        if ($aiPlan.data.ai_used) {
            throw 'Packaged AI planner unexpectedly used AI while fallback was required.'
        }
        if (-not [string]$aiPlan.data.fallback_reason) {
            throw 'Packaged AI planner fell back without an explanatory reason.'
        }
    }

    $media = Invoke-RestMethod -Uri "$BaseUrl/api/media/library" -TimeoutSec 5
    if ($media.data.synth_count -lt 4 -or $media.data.playable_count -lt 4) {
        throw 'Packaged synthesized sound library is incomplete'
    }

    $photoBytes = [IO.File]::ReadAllBytes((Join-Path $ProjectRoot 'pictures\focus.png'))
    $imageData = 'data:image/png;base64,' + [Convert]::ToBase64String($photoBytes)
    $petBody = @{
        name = 'SmokeBuddy'
        image = $imageData
    } | ConvertTo-Json -Compress
    $created = Invoke-RestMethod -Uri "$BaseUrl/api/pet/custom/create" -Method Post `
        -ContentType 'application/json; charset=utf-8' -Body $petBody -TimeoutSec 20
    $skin = [string]$created.data.pet.skin
    if (-not $skin.StartsWith('custom:')) {
        throw 'Packaged custom pet was not selected'
    }
    $catalogItem = $created.data.cat_skins |
        Where-Object { $_.id -eq $skin } |
        Select-Object -First 1
    if (-not $catalogItem -or $catalogItem.stage_assets.Count -ne 4) {
        throw 'Packaged custom pet growth assets are incomplete'
    }
    $assetResponse = Invoke-WebRequest -Uri ($BaseUrl + $catalogItem.stage_assets[3]) `
        -TimeoutSec 5 -UseBasicParsing
    if ($assetResponse.StatusCode -ne 200 -or $assetResponse.RawContentLength -lt 1000) {
        throw 'Packaged custom pet asset could not be served'
    }

    $customId = $skin.Substring('custom:'.Length)
    $deleteBody = @{ id = $customId } | ConvertTo-Json -Compress
    $deleted = Invoke-RestMethod -Uri "$BaseUrl/api/pet/custom/delete" -Method Post `
        -ContentType 'application/json; charset=utf-8' -Body $deleteBody
    if ($deleted.data.pet.skin -ne 'orange') {
        throw 'Deleting the selected custom pet did not restore a built-in pet'
    }

    [pscustomobject]@{
        Api = $BaseUrl
        HealthService = $Health.data.service
        HealthVersion = $Health.data.version
        AIUsed = [bool]$aiPlan.data.ai_used
        AISource = $aiPlan.data.source
        AIFallbackReason = $aiPlan.data.fallback_reason
        GoalTargets = $values -join ', '
        Scenarios = $plan.data.scenes.Count
        SynthesizedAudio = $media.data.synth_count
        LocalAudioFiles = $media.data.file_count
        CustomGrowthAssets = $catalogItem.stage_assets.Count
        CustomPetDeleteFallback = $deleted.data.pet.skin
    } | Format-List

    Invoke-RestMethod -Uri "$BaseUrl/api/shutdown" -Method Post `
        -ContentType 'application/json' -Body '{}' | Out-Null
    $Process.WaitForExit(5000) | Out-Null
} finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
    }
    Remove-Item Env:FOCUS_BUDDY_NO_BROWSER -ErrorAction SilentlyContinue
    Remove-Item Env:FOCUS_AGENT_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:FOCUS_BUDDY_OLLAMA_URL -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $DataRoot) {
        Remove-Item -LiteralPath $DataRoot -Recurse -Force
    }
}
