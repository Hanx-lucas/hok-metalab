param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$siteRoot = Join-Path $projectRoot 'site\dist'
$portfolioUrl = 'http://127.0.0.1:4173/'

function Test-PortfolioReady {
    try {
        $response = Invoke-WebRequest -Uri $portfolioUrl -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -eq 200 -and $response.Content -match 'MetaLab')
    } catch { return $false }
}

if (-not (Test-Path -LiteralPath (Join-Path $siteRoot 'index.html'))) {
    throw 'Website files missing. Restore site/dist or open output/portfolio/index.html.'
}

if (-not (Test-PortfolioReady)) {
    $listener = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 4173 is in use by another service. Open output/portfolio/index.html instead.' }

    $pythonExecutable = $null
    $pythonPrefix = @()
    foreach ($candidate in @(
        (Join-Path $projectRoot '.venv\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate) { $pythonExecutable = $candidate; break }
    }
    if (-not $pythonExecutable) {
        $command = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($command) { $pythonExecutable = $command.Source }
        else {
            $command = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($command) { $pythonExecutable = $command.Source; $pythonPrefix = @('-3') }
        }
    }
    if (-not $pythonExecutable) {
        throw 'Python not found. Open output/portfolio/index.html for the offline version.'
    }

    $logRoot = Join-Path $projectRoot 'output\server'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $arguments = $pythonPrefix + @('-u', '-m', 'http.server', '4173', '--bind', '127.0.0.1', '--directory', ('"{0}"' -f $siteRoot))
    $serverProcess = Start-Process -FilePath $pythonExecutable -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'stdout.log') -RedirectStandardError (Join-Path $logRoot 'stderr.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-PortfolioReady) { $ready = $true; break }
        if ($serverProcess.HasExited) { break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
        if (-not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue }
        throw 'Server did not start. See output/server/stderr.log or use the offline version.'
    }
    @{pid = $serverProcess.Id; url = $portfolioUrl; directory = $siteRoot; startedAt = (Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot 'server-state.json') -Encoding UTF8
}

Write-Host "Portfolio ready: $portfolioUrl"
Write-Host 'The server runs in the background. Run this launcher again after restarting Windows.'
if (-not $NoBrowser) { Start-Process $portfolioUrl }
