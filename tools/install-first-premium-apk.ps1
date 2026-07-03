param(
    [string]$Apk = "",
    [string]$Adb = "E:\android\Sdk\platform-tools\adb.exe",
    [string]$Package = "com.example.first",
    [string]$Activity = ".MainActivity",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Apk)) {
    $Apk = Join-Path $ProjectRoot "output\first-premium-debug.apk"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot "output"
}

function Log([string]$Message) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message"
}

if (-not (Test-Path -LiteralPath $Adb)) {
    throw "adb not found: $Adb"
}
if (-not (Test-Path -LiteralPath $Apk)) {
    throw "APK not found: $Apk"
}

New-Item -ItemType Directory -Force $OutputDir | Out-Null

Log "Checking connected Android devices"
$devices = & $Adb devices -l
$devices | Tee-Object -FilePath (Join-Path $OutputDir "first-premium-adb-devices.txt") | Out-Host

$readyDevices = $devices | Select-String -Pattern "device\s" | Where-Object { $_.Line -notmatch "^List of devices" }
if (-not $readyDevices) {
    throw "No authorized Android device or emulator is connected. Start an emulator or connect a device, then rerun this script."
}

Log "Installing APK: $Apk"
& $Adb install -r $Apk | Tee-Object -FilePath (Join-Path $OutputDir "first-premium-install.txt") | Out-Host

Log "Starting $Package/$Activity"
& $Adb shell am start -n "$Package/$Activity" | Tee-Object -FilePath (Join-Path $OutputDir "first-premium-start.txt") | Out-Host

Start-Sleep -Seconds 5

Log "Capturing screenshot"
& $Adb exec-out screencap -p > (Join-Path $OutputDir "first-premium-screenshot.png")

Log "Capturing recent app logs"
& $Adb logcat -d -t 300 | Select-String -Pattern "AndroidRuntime|FATAL|$Package|Billing|Premium" |
    Tee-Object -FilePath (Join-Path $OutputDir "first-premium-logcat.txt") | Out-Host

Log "Done"
