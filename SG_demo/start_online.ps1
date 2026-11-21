# Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\start_online.ps1
[CmdletBinding()]
param(
    [string]$Python = 'D:\.conda\torch\python.exe',
    [string]$Cloudflared,
    [int]$Port = 8877,
    [string]$FrontendOrigin = 'https://sgdemo-theta.vercel.app'
)
$ErrorActionPreference = 'Stop'
if (-not $Cloudflared) { $Cloudflared = Join-Path $PSScriptRoot 'tools\cloudflared.exe' }
$backend = $null
try {
    if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
    if (-not (Test-Path -LiteralPath $Cloudflared)) { throw "Install cloudflared at $Cloudflared first. See ONLINE.md." }
    $envRoot = Split-Path -Parent $Python
    $env:PATH = "$envRoot\Library\bin;$envRoot\DLLs;" + $env:PATH
    $env:OPENBLAS_NUM_THREADS = '1'
    $env:OMP_NUM_THREADS = '1'
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes = New-Object byte[] 24
    $random.GetBytes($bytes)
    $random.Dispose()
    $env:TWIN_ACCESS_TOKEN = [Convert]::ToBase64String($bytes)
    # Never reuse an unknown service on an occupied port.
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $probe.Start() } finally { $probe.Stop() }
    $logDir = Join-Path $PSScriptRoot 'logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $backend = Start-Process -FilePath $Python -ArgumentList @('-u', 'twin_server.py', '--port', "$Port", '--allow-origin', $FrontendOrigin) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logDir\online-$stamp-out.log" -RedirectStandardError "$logDir\online-$stamp-error.log"
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($backend.HasExited) { throw "Backend exited. See $logDir\online-$stamp-error.log" }
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) { throw 'Backend startup timed out.' }
    Write-Host "Frontend: $FrontendOrigin" -ForegroundColor Green
    Write-Host 'Access code (private; enter in the frontend connection form):' -ForegroundColor Yellow
    Write-Host $env:TWIN_ACCESS_TOKEN -ForegroundColor Yellow
    Write-Host 'Copy the https://*.trycloudflare.com URL printed below into the frontend backend-address field.'
    Write-Host 'Keep this terminal open. Ctrl+C stops the tunnel and backend. Restarting changes the URL and access code.'
    & $Cloudflared tunnel --url "http://127.0.0.1:$Port" --protocol http2 --no-autoupdate
    if ($LASTEXITCODE -ne 0) { throw "Tunnel exited with code $LASTEXITCODE" }
} finally {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id }
    Remove-Item Env:TWIN_ACCESS_TOKEN -ErrorAction SilentlyContinue
}
