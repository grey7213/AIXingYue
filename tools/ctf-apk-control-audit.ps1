param(
    [string]$Apk = "base.apk",
    [string]$PackageName = "com.flai.flai",
    [string]$LaunchActivity = "com.flai.flai.MainActivity",
    [string]$DecodedDir = "reverse-analysis\base-apk\unpacked",
    [string]$OutDir = "reverse-analysis\ctf-control-audit",
    [switch]$Install,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Resolve-Tool {
    param([string[]]$Candidates, [string]$Name)
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Run-Capture {
    param([string]$Exe, [string[]]$ArgList, [switch]$AllowFail)
    function Quote-Arg {
        param([string]$Arg)
        if ($null -eq $Arg) { return '""' }
        if ($Arg -match '[\s"]') {
            return '"' + ($Arg -replace '"', '\"') + '"'
        }
        return $Arg
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = (($ArgList | ForEach-Object { Quote-Arg $_ }) -join " ")
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    $text = (($stdout, $stderr) -join "`n").Trim()
    if (($p.ExitCode -ne 0) -and -not $AllowFail) {
        throw "Command failed ($($p.ExitCode)): $Exe $($ArgList -join ' ')`n$text"
    }
    return [pscustomobject]@{ ExitCode = $p.ExitCode; Text = $text }
}

function Add-Report {
    param([string]$Text)
    Add-Content -LiteralPath $script:ReportPath -Value $Text -Encoding UTF8
}

$Workspace = (Resolve-Path ".").Path
$ApkPath = (Resolve-Path $Apk).Path
$DecodedPath = (Resolve-Path $DecodedDir).Path
$OutPath = Join-Path $Workspace $OutDir
New-Item -ItemType Directory -Force -Path $OutPath | Out-Null

$ReportPath = Join-Path $OutPath "audit-report.md"
$script:ReportPath = $ReportPath
Set-Content -LiteralPath $ReportPath -Value "# CTF APK Control And Integrity Audit`n" -Encoding UTF8
Add-Report "- Time: $(Get-Date -Format s)"
Add-Report "- APK: $ApkPath"
Add-Report "- Package: $PackageName"
Add-Report "- Decoded dir: $DecodedPath"
Add-Report ""

$SdkRoot = $env:ANDROID_SDK_ROOT
if (-not $SdkRoot) { $SdkRoot = $env:ANDROID_HOME }
if (-not $SdkRoot) { $SdkRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk" }
$BuildTools = Join-Path $SdkRoot "build-tools\33.0.2"

$Apktool = Resolve-Tool @((Join-Path $Workspace "tools\apktool\apktool.bat")) "apktool"
$Apksigner = Resolve-Tool @((Join-Path $BuildTools "apksigner.bat")) "apksigner"
$Zipalign = Resolve-Tool @((Join-Path $BuildTools "zipalign.exe")) "zipalign"
$Adb = Resolve-Tool @((Join-Path $SdkRoot "platform-tools\adb.exe")) "adb"
$Keytool = Resolve-Tool @() "keytool"

Add-Report "## Tooling"
foreach ($pair in @(
    @("apktool", $Apktool),
    @("apksigner", $Apksigner),
    @("zipalign", $Zipalign),
    @("adb", $Adb),
    @("keytool", $Keytool)
)) {
    Add-Report "- $($pair[0]): $($pair[1])"
}
Add-Report ""

if (-not $Apktool -or -not $Apksigner -or -not $Zipalign -or -not $Keytool) {
    throw "Required tool missing. See $ReportPath"
}

Add-Report "## Original Signature"
$sig = Run-Capture $Apksigner @("verify", "-v", "--print-certs", $ApkPath) -AllowFail
Add-Report '```text'
Add-Report $sig.Text
Add-Report '```'
Add-Report ""

Add-Report "## Local Workspace Control"
$canWrite = $false
$probe = Join-Path $OutPath "write-probe.txt"
try {
    Set-Content -LiteralPath $probe -Value "write-ok" -Encoding ASCII
    $canWrite = (Test-Path $probe)
} catch {
    $canWrite = $false
}
Add-Report "- Can write audit workspace: $canWrite"
Add-Report "- Can modify decoded APK copy: tested during rebuild step below."
Add-Report ""

Add-Report "## adb And Runtime Privilege"
if ($Adb) {
    $devices = Run-Capture $Adb @("devices", "-l") -AllowFail
    Add-Report '```text'
    Add-Report $devices.Text
    Add-Report '```'
    $deviceLines = @($devices.Text -split "`r?`n" | Where-Object { $_ -match "\sdevice(\s|$)" -and $_ -notmatch "^List of" })
    if ($deviceLines.Count -gt 0) {
        $uid = Run-Capture $Adb @("shell", "id") -AllowFail
        $su = Run-Capture $Adb @("shell", "su", "-c", "id") -AllowFail
        Add-Report "- adb.shell.id: `$($uid.Text)`"
        Add-Report "- adb.su.id: `$($su.Text)`"
        Add-Report "- adb.root.available: $($su.Text -match 'uid=0')"
    } else {
        Add-Report "- adb.connected.device: false"
        Add-Report "- adb.root.available: unverified, no connected device/emulator"
    }
} else {
    Add-Report "- adb: missing"
}
Add-Report ""

Add-Report "## Static Protection Boundary"
$manifest = Join-Path $DecodedPath "AndroidManifest.xml"
$stub = Join-Path $DecodedPath "smali\com\stub\StubApp.smali"
$jiaguAssets = Get-ChildItem -LiteralPath (Join-Path $DecodedPath "assets") -Filter "libjiagu*.so" -ErrorAction SilentlyContinue
$jgapp = Join-Path $DecodedPath "assets\.jgapp"
Add-Report "- Manifest Application class contains StubApp: $((Get-Content -Raw $manifest) -match 'com\.stub\.StubApp')"
Add-Report "- StubApp exists: $(Test-Path $stub)"
Add-Report "- jiagu native assets: $(@($jiaguAssets | ForEach-Object { $_.Name }) -join ', ')"
Add-Report "- .jgapp marker exists: $(Test-Path $jgapp)"
if (Test-Path $stub) {
    $stubText = Get-Content -Raw $stub
    Add-Report "- Stub loads native jiagu library: $($stubText -match 'loadLibrary')"
    Add-Report "- Stub extracts to private .jiagu dir: $($stubText -match '/\.jiagu')"
    Add-Report "- Stub can terminate process on missing real Application: $($stubText -match 'System;->exit')"
}
Add-Report ""

if (-not $SkipBuild) {
    Add-Report "## Minimal Tamper, Rebuild, Align, Resign"
    $WorkDecoded = Join-Path $OutPath "decoded-mutated"
    if (Test-Path $WorkDecoded) { Remove-Item -LiteralPath $WorkDecoded -Recurse -Force }
    Copy-Item -LiteralPath $DecodedPath -Destination $WorkDecoded -Recurse

    $AsciiBuildRoot = Join-Path $env:TEMP "ctf-apk-control-audit"
    $AsciiDecoded = Join-Path $AsciiBuildRoot "decoded-mutated"
    if (Test-Path $AsciiBuildRoot) { Remove-Item -LiteralPath $AsciiBuildRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $AsciiBuildRoot | Out-Null
    Copy-Item -LiteralPath $WorkDecoded -Destination $AsciiDecoded -Recurse

    $MarkerPath = Join-Path $WorkDecoded "assets\ctf_tamper_marker.txt"
    Set-Content -LiteralPath $MarkerPath -Value "ctf-tamper-marker $(Get-Date -Format s)" -Encoding ASCII
    $AsciiMarkerPath = Join-Path $AsciiDecoded "assets\ctf_tamper_marker.txt"
    Set-Content -LiteralPath $AsciiMarkerPath -Value (Get-Content -Raw -LiteralPath $MarkerPath) -Encoding ASCII
    Add-Report "- Tamper marker added: $MarkerPath"
    Add-Report "- ASCII build workspace: $AsciiDecoded"

    $UnsignedApk = Join-Path $AsciiBuildRoot "mutated-unsigned.apk"
    $AlignedApk = Join-Path $AsciiBuildRoot "mutated-aligned.apk"
    $SignedApk = Join-Path $AsciiBuildRoot "mutated-signed.apk"
    $FinalUnsignedApk = Join-Path $OutPath "mutated-unsigned.apk"
    $FinalAlignedApk = Join-Path $OutPath "mutated-aligned.apk"
    $FinalSignedApk = Join-Path $OutPath "mutated-signed.apk"
    foreach ($f in @($UnsignedApk, $AlignedApk, $SignedApk, $FinalUnsignedApk, $FinalAlignedApk, $FinalSignedApk)) {
        if (Test-Path $f) { Remove-Item -LiteralPath $f -Force }
    }

    $build = Run-Capture $Apktool @("b", $AsciiDecoded, "-o", $UnsignedApk) -AllowFail
    Add-Report "### apktool build"
    Add-Report '```text'
    Add-Report $build.Text
    Add-Report '```'
    Add-Report "- apktool.build.success: $(($build.ExitCode -eq 0) -and (Test-Path $UnsignedApk))"

    if (($build.ExitCode -eq 0) -and (Test-Path $UnsignedApk)) {
        $align = Run-Capture $Zipalign @("-f", "-p", "4", $UnsignedApk, $AlignedApk) -AllowFail
        Add-Report "### zipalign"
        Add-Report '```text'
        Add-Report $align.Text
        Add-Report '```'
        Add-Report "- zipalign.success: $(($align.ExitCode -eq 0) -and (Test-Path $AlignedApk))"

        $Keystore = Join-Path $OutPath "ctf-test.keystore"
        $Alias = "ctfkey"
        $StorePass = "ctfpass123"
        if (-not (Test-Path $Keystore)) {
            $keygen = Run-Capture $Keytool @(
                "-genkeypair",
                "-keystore", $Keystore,
                "-storepass", $StorePass,
                "-keypass", $StorePass,
                "-alias", $Alias,
                "-keyalg", "RSA",
                "-keysize", "2048",
                "-validity", "3650",
                "-dname", "CN=CTF,O=Sandbox"
            ) -AllowFail
            Add-Report "### keytool"
            Add-Report '```text'
            Add-Report $keygen.Text
            Add-Report '```'
        }

        $sign = Run-Capture $Apksigner @(
            "sign",
            "--ks", $Keystore,
            "--ks-key-alias", $Alias,
            "--ks-pass", "pass:$StorePass",
            "--key-pass", "pass:$StorePass",
            "--out", $SignedApk,
            $AlignedApk
        ) -AllowFail
        Add-Report "### apksigner sign"
        Add-Report '```text'
        Add-Report $sign.Text
        Add-Report '```'
        Add-Report "- apksigner.sign.success: $(($sign.ExitCode -eq 0) -and (Test-Path $SignedApk))"

        if (Test-Path $SignedApk) {
            Copy-Item -LiteralPath $UnsignedApk -Destination $FinalUnsignedApk -Force
            Copy-Item -LiteralPath $AlignedApk -Destination $FinalAlignedApk -Force
            Copy-Item -LiteralPath $SignedApk -Destination $FinalSignedApk -Force
            $verify = Run-Capture $Apksigner @("verify", "-v", "--print-certs", $SignedApk) -AllowFail
            Add-Report "### signed APK verify"
            Add-Report '```text'
            Add-Report $verify.Text
            Add-Report '```'
            Add-Report "- signed.apk: $FinalSignedApk"
            Add-Report "- signed.apk.signature.verifies: $($verify.Text -match '^Verifies')"
        }

        if ($Install -and $Adb -and (Test-Path $SignedApk)) {
            Add-Report "## Optional Device Install And Launch"
            $installResult = Run-Capture $Adb @("install", "-r", "-d", $SignedApk) -AllowFail
            Add-Report "### adb install"
            Add-Report '```text'
            Add-Report $installResult.Text
            Add-Report '```'
            Add-Report "- adb.install.success: $($installResult.Text -match 'Success')"

            Run-Capture $Adb @("logcat", "-c") -AllowFail | Out-Null
            $component = "$PackageName/$LaunchActivity"
            $startResult = Run-Capture $Adb @("shell", "am", "start", "-n", $component) -AllowFail
            Start-Sleep -Seconds 5
            $logResult = Run-Capture $Adb @("logcat", "-d", "-t", "500") -AllowFail
            Add-Report "### adb start"
            Add-Report '```text'
            Add-Report $startResult.Text
            Add-Report '```'
            Add-Report "### recent logcat"
            Add-Report '```text'
            Add-Report $logResult.Text
            Add-Report '```'
            Add-Report "- runtime.protection.hints: search logcat for `StubApp`, `jiagu`, `UnsatisfiedLinkError`, `Failed to call attachBaseContext`, `SecurityException`, `signature`."
        }
    }
}

Add-Report ""
Add-Report "## Interpretation"
Add-Report "- Passing local rebuild/resign proves file-level control and APK package-signature integrity regeneration with a new key."
Add-Report "- It does not prove the original jiagu/native runtime protection chain is bypassed. That requires installation and successful launch on a device while observing that `StubApp.attachBaseContext()` loads `libjiagu*.so`, reconstructs the real Application, and does not abort."
Add-Report "- Production update/store equivalence cannot be claimed with the temporary CTF key because the signer certificate digest differs from the original. Same-package upgrade over the original app and app-store identity continuity require the original signing lineage/key or a platform/store-managed key path."

Write-Output "Audit complete: $ReportPath"
