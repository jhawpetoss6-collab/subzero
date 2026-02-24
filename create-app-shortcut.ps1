$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\SubZero App.lnk")

# Try Edge first (app mode), fall back to Chrome
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"

if (Test-Path $edge) {
    $Shortcut.TargetPath = $edge
} elseif (Test-Path $chrome) {
    $Shortcut.TargetPath = $chrome
} else {
    Write-Host "No Edge or Chrome found!" -ForegroundColor Red
    exit 1
}

$Shortcut.Arguments = "--app=https://jhawpetoss6-collab.github.io/subzero/ --window-size=420,900"
$Shortcut.IconLocation = "C:\Users\jhawp\subzero\subzero.ico"
$Shortcut.WorkingDirectory = "C:\Users\jhawp\subzero"
$Shortcut.Description = "SubZero - Flawless Victory"
$Shortcut.Save()

Write-Host "SubZero App shortcut created on Desktop!" -ForegroundColor Green
