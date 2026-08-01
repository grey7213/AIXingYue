[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status', 'reset')]
    [string]$Action = 'start',
    [switch]$NoBrowser,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$manager = Join-Path $PSScriptRoot 'offline_dev.py'

if (-not (Test-Path -LiteralPath $manager -PathType Leaf)) {
    Write-Error "Offline manager not found: $manager"
    exit 2
}

$runner = $null
$runnerPrefix = @()

$preferredPython = 'D:\Anconda3\python.exe'
if (Test-Path -LiteralPath $preferredPython -PathType Leaf) {
    & $preferredPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $runner = $preferredPython
    }
}

if (-not $runner -and (Get-Command py -ErrorAction SilentlyContinue)) {
    & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $runner = 'py'
        $runnerPrefix = @('-3')
    }
}

if (-not $runner -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $runner = 'python'
    }
}

if (-not $runner) {
    Write-Error 'Python 3.10 or newer was not found. Install Python, then run this entry again.'
    exit 2
}

$arguments = @($runnerPrefix) + @($manager, $Action)
if ($Action -eq 'status' -and $Json) {
    $arguments += '--json'
}

& $runner @arguments
$code = $LASTEXITCODE

if ($code -eq 0 -and $Action -eq 'start' -and -not $NoBrowser) {
    Start-Process 'http://127.0.0.1:8080/app/login.html'
}

exit $code
