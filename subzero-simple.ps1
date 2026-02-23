# SubZero - Ultra Simple
# Just close the window when done

# Cast file for ScreenCast in SubZero Terminal Dark
$castDir = Join-Path $env:USERPROFILE ".subzero"
if (-not (Test-Path $castDir)) { New-Item -ItemType Directory -Path $castDir -Force | Out-Null }
$castFile = Join-Path $castDir "subzero_cast.txt"
$castLog = ""

Clear-Host
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "          SubZero AI Terminal" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Close window when done (or type Ctrl+C)" -ForegroundColor Gray
Write-Host ""

# Write initial header to cast file
$castLog = "== SubZero AI Terminal =="
$castLog | Set-Content -Path $castFile -Encoding UTF8

try {
    while ($true) {
        Write-Host "You: " -NoNewline -ForegroundColor Cyan
        $q = Read-Host

        if ($q) {
            Write-Host ""
            Write-Host "SubZero: " -ForegroundColor Green
            $response = ollama run qwen2.5:1.5b $q
            $response
            Write-Host ""

            # Append exchange to cast log and write to file
            $castLog += "`nYou: $q`nSubZero: $response`n"
            $castLog | Set-Content -Path $castFile -Encoding UTF8
        }
    }
} finally {
    # Clean up cast file when terminal closes
    if (Test-Path $castFile) { Remove-Item $castFile -Force -ErrorAction SilentlyContinue }
}
