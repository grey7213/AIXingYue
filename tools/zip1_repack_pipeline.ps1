param(
    [switch]$Install,
    [switch]$ForceDecode,
    [switch]$ClearData,
    [string]$ServerUrl,
    [string]$Python = "D:\Anconda3\python.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "tools\zip1_repack_pipeline.py"

if (!(Test-Path $Python)) {
    $Python = "python"
}

$ArgsList = @($Script)
if ($Install) {
    $ArgsList += "--install"
}
if ($ForceDecode) {
    $ArgsList += "--force-decode"
}
if ($ClearData) {
    $ArgsList += "--clear-data"
}
if ($ServerUrl) {
    $ArgsList += "--server-url"
    $ArgsList += $ServerUrl
}

& $Python @ArgsList
exit $LASTEXITCODE
