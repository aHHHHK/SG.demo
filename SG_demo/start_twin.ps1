# Run from PowerShell or PyCharm terminal: .\start_twin.ps1
param([int]$Port = 8765, [string]$Python = 'D:\.conda\torch\python.exe')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python. Pass -Python with your scipy/iapws environment."
}
# Windows Conda DLL search path is required for SciPy's linear algebra backend.
$twinEnvRoot = Split-Path -Parent $Python
$env:PATH = "$twinEnvRoot\Library\bin;$twinEnvRoot\DLLs;" + $env:PATH
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& $Python (Join-Path $PSScriptRoot 'twin_server.py') --port $Port
