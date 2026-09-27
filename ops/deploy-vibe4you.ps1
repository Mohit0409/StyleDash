[CmdletBinding()]
param(
    [ValidatePattern('^[0-9a-fA-F]{7,40}$')]
    [string]$Commit,
    [switch]$PreflightOnly,
    [switch]$Status,
    [switch]$Resume,
    [string]$SshHost = $(if ($env:STYLEDASH_DEPLOY_SSH_HOST) { $env:STYLEDASH_DEPLOY_SSH_HOST } else { 'u0_a324@192.168.1.7' }),
    [int]$SshPort = $(if ($env:STYLEDASH_DEPLOY_SSH_PORT) { [int]$env:STYLEDASH_DEPLOY_SSH_PORT } else { 8022 }),
    [string]$SshIdentity = $(if ($env:STYLEDASH_DEPLOY_SSH_IDENTITY) { $env:STYLEDASH_DEPLOY_SSH_IDENTITY } else { Join-Path $env:USERPROFILE '.ssh\codex_styledash_termux' })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Repository = 'Mohit0409/StyleDash'
$RequiredCheck = 'StyleDash Required CI'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptRoot '..')).Path
$SshArgs = @('-i', $SshIdentity, '-p', "$SshPort", '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15')
$ScpArgs = @('-i', $SshIdentity, '-P', "$SshPort", '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15')

function Invoke-Native {
    param([Parameter(Mandatory)][string]$Command, [Parameter(Mandatory)][string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-LoggedNative {
    param([Parameter(Mandatory)][string]$Command, [Parameter(Mandatory)][string[]]$Arguments, [Parameter(Mandatory)][string]$LogPath)
    & $Command @Arguments *>&1 | Tee-Object -LiteralPath $LogPath -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE. Detailed log: $LogPath"
    }
}

function Invoke-Ssh {
    param([Parameter(Mandatory)][string]$RemoteCommand)
    & ssh @SshArgs $SshHost $RemoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed with exit code $LASTEXITCODE"
    }
}

function Show-Status {
    Invoke-Ssh 'if [ -x "$HOME/bin/vibe-deploy" ]; then "$HOME/bin/vibe-deploy" --status; else echo "STATE                    IDLE_OR_NOT_INSTALLED"; fi'
}

if ($Status) {
    Show-Status
    exit 0
}

if (!(Test-Path -LiteralPath $SshIdentity -PathType Leaf)) {
    throw "Supported Vibe4You SSH identity file was not found: $SshIdentity"
}

Push-Location $RepoRoot
$TempRoot = $null
try {
    Invoke-Native git @('fetch', 'origin')
    $OriginMain = (& git rev-parse 'origin/main').Trim()
    if ($LASTEXITCODE -ne 0 -or $OriginMain -notmatch '^[0-9a-f]{40}$') {
        throw 'Could not resolve origin/main.'
    }
    $ReleaseSha = if ($Commit) { (& git rev-parse "$Commit^{commit}").Trim().ToLowerInvariant() } else { $OriginMain.ToLowerInvariant() }
    if ($LASTEXITCODE -ne 0 -or $ReleaseSha -notmatch '^[0-9a-f]{40}$') {
        throw 'The requested commit does not resolve to a full Git commit.'
    }
    & git merge-base --is-ancestor $ReleaseSha 'origin/main'
    if ($LASTEXITCODE -ne 0) {
        throw 'UNAPPROVED_SHA: the requested commit is not merged into origin/main.'
    }

    $CheckJson = & gh api -H 'Accept: application/vnd.github+json' "repos/$Repository/commits/$ReleaseSha/check-runs"
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CI evidence could not be loaded.' }
    $Checks = ($CheckJson | ConvertFrom-Json).check_runs
    $Required = @($Checks | Where-Object { $_.name -eq $RequiredCheck -and $_.head_sha -eq $ReleaseSha } | Sort-Object completed_at -Descending)
    if ($Required.Count -eq 0 -or $Required[0].status -ne 'completed' -or $Required[0].conclusion -ne 'success') {
        throw "CI_NOT_GREEN: $RequiredCheck has not passed for exact SHA $ReleaseSha."
    }
    $CiRunUrl = [string]$Required[0].details_url
    if ($CiRunUrl -notmatch '/actions/runs/(\d+)(?:/|$)') { throw 'Required CI run URL is invalid.' }
    $CiRunId = $Matches[1]
    $RunJson = & gh api -H 'Accept: application/vnd.github+json' "repos/$Repository/actions/runs/$CiRunId"
    if ($LASTEXITCODE -ne 0) { throw 'Required GitHub Actions run evidence could not be loaded.' }
    $Run = $RunJson | ConvertFrom-Json
    if ($Run.head_sha -ne $ReleaseSha -or $Run.name -ne 'Vibe4You CI' -or $Run.path -ne '.github/workflows/ci.yml' -or $Run.status -ne 'completed' -or $Run.conclusion -ne 'success') {
        throw 'CI_NOT_GREEN: required workflow identity or exact-SHA run evidence is invalid.'
    }
    $JobsJson = & gh api -H 'Accept: application/vnd.github+json' "repos/$Repository/actions/runs/$CiRunId/jobs"
    if ($LASTEXITCODE -ne 0) { throw 'Required GitHub Actions job evidence could not be loaded.' }
    $RequiredJob = @((($JobsJson | ConvertFrom-Json).jobs) | Where-Object { $_.name -eq $RequiredCheck -and $_.status -eq 'completed' -and $_.conclusion -eq 'success' })
    if ($RequiredJob.Count -ne 1) { throw 'CI_NOT_GREEN: required workflow job did not pass exactly once.' }
    $CommitTimestamp = (& git show -s --format=%cI $ReleaseSha).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($CommitTimestamp)) {
        throw 'Could not determine the immutable release commit timestamp.'
    }

    Write-Host 'Vibe4You Deployment v2'
    Write-Host ''
    Write-Host ("RELEASE_SHA              {0}" -f $ReleaseSha)
    Write-Host ("ORIGIN_MAIN              {0}" -f $OriginMain)
    Write-Host 'MAIN                     VERIFIED'
    Write-Host 'GITHUB_CI                PASS'
    Write-Host ("CI_RUN                   {0}" -f $CiRunUrl)
    Write-Host ("MODE                     {0}" -f $(if ($PreflightOnly) { 'PREFLIGHT ONLY' } elseif ($Resume) { 'RESUME' } else { 'DEPLOY' }))
    Write-Host 'PRODUCTION_DEPLOY        OWNER COMMAND GATE CONFIRMED'
    Write-Host ''

    $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vibe4you-deploy-{0}-{1}" -f $ReleaseSha.Substring(0, 12), [guid]::NewGuid().ToString('N'))
    $OwnerLogRoot = Join-Path $env:LOCALAPPDATA 'Vibe4You\deployment-logs'
    New-Item -ItemType Directory -Force -Path $OwnerLogRoot | Out-Null
    $OwnerLog = Join-Path $OwnerLogRoot ("deploy-{0}-{1}.log" -f $ReleaseSha.Substring(0, 12), (Get-Date -Format 'yyyyMMddTHHmmssZ'))
    Write-Host ("DETAIL_LOG               {0}" -f $OwnerLog)
    $Checkout = Join-Path $TempRoot 'source'
    $Artifacts = Join-Path $TempRoot 'artifacts'
    New-Item -ItemType Directory -Path $Checkout, $Artifacts | Out-Null
    $SourceTar = Join-Path $TempRoot 'source.tar'
    Invoke-Native git @('archive', '--format=tar', "--output=$SourceTar", $ReleaseSha)
    Invoke-Native tar @('-xf', $SourceTar, '-C', $Checkout)

    $AllowedVite = @(
        'VITE_BRAND_NAME',
        'VITE_FIREBASE_API_KEY',
        'VITE_FIREBASE_AUTH_DOMAIN',
        'VITE_FIREBASE_PROJECT_ID',
        'VITE_FIREBASE_APP_ID',
        'VITE_GA_MEASUREMENT_ID',
        'VITE_META_PIXEL_ID'
    )
    $PrivateBuildEnv = Join-Path $RepoRoot '.env'
    if (!(Test-Path -LiteralPath $PrivateBuildEnv -PathType Leaf)) {
        throw 'Private local production frontend build configuration (.env) is missing.'
    }
    foreach ($Line in Get-Content -LiteralPath $PrivateBuildEnv) {
        if ($Line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$' -and $AllowedVite -contains $Matches[1]) {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
        }
    }
    foreach ($Name in @('VITE_FIREBASE_API_KEY', 'VITE_FIREBASE_AUTH_DOMAIN', 'VITE_FIREBASE_PROJECT_ID', 'VITE_FIREBASE_APP_ID')) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, 'Process'))) {
            throw "Production frontend configuration is incomplete: $Name"
        }
    }

    Push-Location $Checkout
    try {
        Write-Host 'ARTIFACT_BUILD           RUNNING'
        Invoke-LoggedNative npm.cmd @('ci', '--no-audit', '--no-fund') $OwnerLog
        Invoke-LoggedNative npm.cmd @('run', 'build') $OwnerLog
        Write-Host 'ARTIFACT_BUILD           PASS'
    }
    finally {
        Pop-Location
    }

    $Artifact = Join-Path $Artifacts ("vibe4you-{0}.tar.gz" -f $ReleaseSha)
    $PullRequestArgs = @()
    $PullUrls = @(& gh api -H 'Accept: application/vnd.github+json' "repos/$Repository/commits/$ReleaseSha/pulls" --jq '.[].html_url')
    foreach ($PullUrl in $PullUrls) {
        if ($PullUrl) { $PullRequestArgs += @('--pull-request', $PullUrl) }
    }
    $BuilderArgs = @(
        (Join-Path $Checkout 'scripts\build_deployment_artifact.py'),
        '--source', $Checkout,
        '--output', $Artifact,
        '--release-sha', $ReleaseSha,
        '--repository', $Repository,
        '--ci-run-id', $CiRunId,
        '--ci-url', $CiRunUrl,
        '--created-at', $CommitTimestamp
    ) + $PullRequestArgs
    Invoke-Native python $BuilderArgs
    $ArtifactHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact).Hash.ToLowerInvariant()
    Write-Host ("ARTIFACT_SHA256         {0}" -f $ArtifactHash)

    $RemoteDirectory = ".local/share/styledash/deployments/incoming/$ReleaseSha"
    Invoke-Ssh "mkdir -p -- \"`$HOME/$RemoteDirectory\" && chmod 700 \"`$HOME/$RemoteDirectory\""
    $Runner = Join-Path $Checkout 'scripts\termux\vibe-deploy'
    $PythonRunner = Join-Path $Checkout 'scripts\termux\vibe_deploy.py'
    & scp @ScpArgs $Runner $PythonRunner $Artifact "$Artifact.sha256" "${SshHost}:$RemoteDirectory/"
    if ($LASTEXITCODE -ne 0) { throw 'Artifact upload failed.' }
    $RemoteArtifact = "`$HOME/$RemoteDirectory/$([IO.Path]::GetFileName($Artifact))"
    $RemoteRunner = "`$HOME/$RemoteDirectory/vibe-deploy"
    Invoke-Ssh "chmod 700 \"$RemoteRunner\"; chmod 600 \"`$HOME/$RemoteDirectory/vibe_deploy.py\" \"$RemoteArtifact\" \"$RemoteArtifact.sha256\""

    if ($PreflightOnly) {
        Invoke-Ssh "\"$RemoteRunner\" --preflight-only \"$RemoteArtifact\""
        exit 0
    }

    $RemoteMode = if ($Resume) { '--resume' } else { '--deploy' }
    Invoke-Ssh "\"$RemoteRunner\" $RemoteMode \"$RemoteArtifact\""

    $Deadline = [DateTime]::UtcNow.AddHours(2)
    $RemoteStatus = '"$HOME/bin/vibe-deploy" --status 2>/dev/null || python3 "$HOME/.local/share/styledash/deployments/incoming/' + $ReleaseSha + '/vibe_deploy.py" --status'
    do {
        Start-Sleep -Seconds 10
        try {
            $StatusLines = @(& ssh @SshArgs $SshHost $RemoteStatus)
            if ($LASTEXITCODE -ne 0) { throw 'status connection failed' }
            $StatusLines | ForEach-Object { Write-Host $_ }
            $ResultLine = $StatusLines | Where-Object { $_ -match '^RESULT\s+' } | Select-Object -Last 1
            $Result = if ($ResultLine) { ($ResultLine -split '\s+', 2)[1].Trim() } else { 'PENDING' }
        }
        catch {
            Write-Warning 'SSH status connection dropped; the detached server task continues. Retrying.'
            $Result = 'PENDING'
        }
    } while ($Result -eq 'PENDING' -and [DateTime]::UtcNow -lt $Deadline)

    if ($Result -ne 'PASS') {
        if ([DateTime]::UtcNow -ge $Deadline) { throw 'Deployment status timed out; run with -Status or -Resume.' }
        throw "Deployment finished with result $Result."
    }

    $RecordLine = $StatusLines | Where-Object { $_ -match '^DEPLOYMENT_RECORD\s+' } | Select-Object -Last 1
    if ($RecordLine) {
        $RemoteRecord = ($RecordLine -split '\s+', 2)[1].Trim()
        $LocalRecords = Join-Path $RepoRoot 'docs\deployments'
        New-Item -ItemType Directory -Force -Path $LocalRecords | Out-Null
        & scp @ScpArgs "${SshHost}:$RemoteRecord" "$LocalRecords\"
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Deployment passed, but the non-sensitive record could not be copied locally.' }
    }
    Write-Host ''
    Write-Host 'DEPLOYMENT PASS'
}
finally {
    Pop-Location
    if ($TempRoot -and (Test-Path -LiteralPath $TempRoot)) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
    }
}
