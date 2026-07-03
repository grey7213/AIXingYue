$ErrorActionPreference = 'Stop'

$Url = 'https://redirector.gvt1.com/edgedl/android/studio/ide-zips/2026.1.1.9/android-studio-quail1-patch1-windows.zip'
$OutDir = 'E:\Android\Downloads'
$OutFile = Join-Path $OutDir 'android-studio-quail1-patch1-windows.zip'
$ExpectedSha256 = '6F0158291F459258420AD7CA70F4B933F51D03E0C0B3C7A6C1BFA89F965184BB'

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Test-Path -LiteralPath $OutFile) {
    Remove-Item -LiteralPath $OutFile -Force
}

Add-Type -AssemblyName System.Net.Http
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromHours(2)
$response = $client.GetAsync($Url, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
$response.EnsureSuccessStatusCode() | Out-Null
$total = $response.Content.Headers.ContentLength

$inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
$outputStream = [System.IO.File]::Open($OutFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    $buffer = New-Object byte[] (1024 * 1024)
    $readTotal = 0L
    $lastReport = [DateTime]::UtcNow.AddSeconds(-10)
    while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $outputStream.Write($buffer, 0, $read)
        $readTotal += $read
        if (([DateTime]::UtcNow - $lastReport).TotalSeconds -ge 5) {
            if ($total) {
                $pct = [math]::Round(($readTotal * 100.0 / $total), 1)
                Write-Host ("downloaded {0:n2} / {1:n2} GB ({2}%)" -f ($readTotal / 1GB), ($total / 1GB), $pct)
            } else {
                Write-Host ("downloaded {0:n2} GB" -f ($readTotal / 1GB))
            }
            $lastReport = [DateTime]::UtcNow
        }
    }
}
finally {
    $outputStream.Dispose()
    $inputStream.Dispose()
    $client.Dispose()
}

$hash = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash
if ($hash -ne $ExpectedSha256) {
    throw "SHA256 mismatch. Expected $ExpectedSha256 but got $hash"
}

Get-Item -LiteralPath $OutFile | Select-Object FullName,@{Name='GB';Expression={[math]::Round($_.Length/1GB,2)}}
Write-Host "sha256 ok: $hash"
