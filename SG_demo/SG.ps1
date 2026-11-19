<#
Usage:
  Double-click SG.bat (recommended; no PowerShell policy setup required).
  Or: powershell -NoProfile -ExecutionPolicy Bypass -File "path\SG.ps1"
  Options: -Port 8765 -Python "C:\path\python.exe" -NoBrowser
  Verification: SG.bat -SmokeTest (starts, tests an SG simulation, then stops).
The script changes to its own directory, selects a free loopback port, starts
both the frontend and API (served by twin_server.py), waits for readiness,
then opens the default browser. Keep the window open; Ctrl+C stops the child.
Occupied ports are skipped; unrelated processes are NEVER terminated.
Requires Python + numpy + matplotlib + pyomo and Conda Library\bin\ipopt.exe.
Logs are stored under logs beside this script. No packages are auto-installed.
#>
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [string]$Python,
    [switch]$NoBrowser,
    [switch]$SmokeTest
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-Location -LiteralPath $PSScriptRoot
$service = $null
$exitStatus = 0
try {
    foreach ($required in @('twin_server.py', 'twin_baseline.py', 'models', 'web/index.html', 'web/app.js', 'web/vendor/three.module.js')) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $required))) {
            throw "Missing project file: $required"
        }
    }
    # Prefer the explicitly selected interpreter, then local/project environments.
    $candidates = @()
    if ($Python) {
        $candidates = @($Python)
    } else {
        $candidates = @((Join-Path $PSScriptRoot '.venv/Scripts/python.exe'))
        if ($env:CONDA_PREFIX) { $candidates += Join-Path $env:CONDA_PREFIX 'python.exe' }
        $candidates += 'D:\.conda\torch\python.exe'
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) { $candidates += $pythonCommand.Source }
    }
    $selectedPython = $null
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $candidateRoot = Split-Path -Parent $candidate
        $env:PATH = "$candidateRoot\Library\bin;$candidateRoot\DLLs;" + $env:PATH
        $env:OPENBLAS_NUM_THREADS = '1'
        $env:OMP_NUM_THREADS = '1'
        & $candidate -c "import numpy, matplotlib, pyomo.environ; import sys; from pathlib import Path; assert (Path(sys.executable).parent / 'Library/bin/ipopt.exe').is_file(), 'Ipopt missing: Library/bin/ipopt.exe'" 2>$null
        if ($LASTEXITCODE -eq 0) { $selectedPython = (Resolve-Path -LiteralPath $candidate).Path; break }
    }
    if (-not $selectedPython) {
        throw 'No compatible Python found. Install numpy, matplotlib, pyomo and Ipopt in a Conda environment, then run SG.bat -Python "C:\path\python.exe".'
    }
    Write-Host "Python: $selectedPython"
    $logDir = Join-Path $PSScriptRoot 'logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdoutLog = Join-Path $logDir "SG-$stamp-out.log"
    $stderrLog = Join-Path $logDir "SG-$stamp-error.log"
    $ready = $false
    # Retry startup if another application wins the small port-selection race.
    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        $selectedPort = $null
        for ($probePort = $Port; $probePort -le [Math]::Min(65535, $Port + 100); $probePort++) {
            $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $probePort)
            try { $probe.Start(); $selectedPort = $probePort; break }
            catch [System.Net.Sockets.SocketException] { }
            finally { $probe.Stop() }
        }
        if ($null -eq $selectedPort) { throw 'No free port found in the requested range.' }
        if ($selectedPort -ne $Port) { Write-Host "Port $Port occupied; using $selectedPort." }
        $url = "http://127.0.0.1:$selectedPort"
        $service = Start-Process -FilePath $selectedPython -ArgumentList @('-u', 'twin_server.py', '--port', "$selectedPort") -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
        $deadline = [DateTime]::UtcNow.AddSeconds(60)
        while ([DateTime]::UtcNow -lt $deadline) {
            if ($service.HasExited) { break }
            try {
                $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 2
                $page = Invoke-WebRequest "$url/" -UseBasicParsing -TimeoutSec 2
                $profiles = Invoke-RestMethod "$url/api/profiles" -TimeoutSec 2
                if ($health.status -eq 'ok' -and $page.StatusCode -eq 200 -and $profiles.SG_qs) {
                    # Confirm the child is still alive, not a service on a raced port.
                    Start-Sleep -Milliseconds 200
                    if (-not $service.HasExited) { $ready = $true; break }
                }
            } catch { }
            Start-Sleep -Milliseconds 300
        }
        if ($ready) { break }
        if (-not $service.HasExited) { throw 'Service readiness timed out (60 seconds).' }
        $failure = Get-Content -LiteralPath $stderrLog -Raw
        if ($failure -match '10048|Address already in use|Only one usage') {
            $Port = $selectedPort + 1
            continue
        }
        throw "Backend exited during startup: $failure"
    }
    if (-not $ready) { throw 'Port conflict persisted after five startup attempts.' }
    foreach ($asset in @('app.js', 'style.css', 'theme-reference.css', 'vendor/three.module.js')) {
        $null = Invoke-WebRequest "$url/$asset" -UseBasicParsing -TimeoutSec 5
    }
    Write-Host "Frontend and backend ready: $url" -ForegroundColor Green
    Write-Host "Logs: $logDir"
    if ($SmokeTest) {
        Write-Host 'Testing SG_qs initialization and qs disturbance...'
        $session = Invoke-RestMethod "$url/api/session" -Method Post -ContentType 'application/json' -Body '{"profile":"SG_qs","ratio":0.001}' -TimeoutSec 180
        if (-not $session.session) { throw 'Simulation session was not created.' }
        $body = @{session=$session.session; action='qs'; ratio=0.001} | ConvertTo-Json
        $result = Invoke-RestMethod "$url/api/action" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
        if (-not $result.snapshot) { throw 'Simulation action returned no snapshot.' }
        Write-Host 'PASS: frontend assets, backend API, SG_qs initialization and qs action.' -ForegroundColor Green
    } else {
        if (-not $NoBrowser) { Start-Process -FilePath $url }
        Write-Host 'Keep this window open. Press Ctrl+C to stop.'
        while (-not $service.HasExited) { Start-Sleep -Milliseconds 500 }
        throw "Backend stopped unexpectedly (exit code $($service.ExitCode))."
    }
} catch {
    Write-Host "SG startup failed: $($_.Exception.Message)" -ForegroundColor Red
    $exitStatus = 1
} finally {
    # Only stop the exact child created by this launcher, never another service.
    if ($service -and -not $service.HasExited) { Stop-Process -InputObject $service -ErrorAction SilentlyContinue }
}
exit $exitStatus
