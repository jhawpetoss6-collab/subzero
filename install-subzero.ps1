# SubZero Studio Professional Installer
# Version 1.0.0

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SubZero Studio Installer v1.0.0" -ForegroundColor Cyan
Write-Host "   Your Personal AI Assistant" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "WARNING: Restarting installer as Administrator..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "OK Administrator access confirmed" -ForegroundColor Green

# Installation paths
$installPath = "$env:ProgramFiles\SubZero Studio"
$userDataPath = "$env:LOCALAPPDATA\SubZero"
$startMenuPath = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\SubZero Studio.lnk"
$desktopPath = "$env:PUBLIC\Desktop\SubZero Studio.lnk"

Write-Host ""
Write-Host "Installing to: $installPath" -ForegroundColor Yellow
Write-Host ""

# Create installation directory
if (Test-Path $installPath) {
    Write-Host "WARNING SubZero Studio is already installed!" -ForegroundColor Yellow
    $response = Read-Host "Reinstall? (Y/N)"
    if ($response -ne "Y" -and $response -ne "y") {
        Write-Host "Installation cancelled." -ForegroundColor Red
        exit
    }
    Write-Host "Removing old installation..." -ForegroundColor Yellow
    Remove-Item -Path $installPath -Recurse -Force
}

Write-Host "Creating installation directory..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $installPath -Force | Out-Null

# Copy files
Write-Host "Copying program files..." -ForegroundColor Cyan
$filesToCopy = @(
    "subzero-studio.ps1",
    "launch-studio.ps1",
    "README.md"
)

foreach ($file in $filesToCopy) {
    if (Test-Path $file) {
        Copy-Item -Path $file -Destination $installPath -Force
        Write-Host "  OK $file" -ForegroundColor Green
    }
    else {
        Write-Host "  WARNING $file not found (skipping)" -ForegroundColor Yellow
    }
}

# Create user data directory
if (-not (Test-Path $userDataPath)) {
    Write-Host "Creating user data directory..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $userDataPath -Force | Out-Null
    New-Item -ItemType Directory -Path "$userDataPath\projects" -Force | Out-Null
    New-Item -ItemType Directory -Path "$userDataPath\books" -Force | Out-Null
    New-Item -ItemType Directory -Path "$userDataPath\audiobooks" -Force | Out-Null
}

# Create launcher script
Write-Host "Creating launcher..." -ForegroundColor Cyan
$launcherPath = "$installPath\SubZero.ps1"
$launcherScript = "Set-Location '$installPath'" + [Environment]::NewLine
$launcherScript += "& '$installPath\launch-studio.ps1'"
Set-Content -Path $launcherPath -Value $launcherScript

# Create Start Menu shortcut
Write-Host "Creating Start Menu shortcut..." -ForegroundColor Cyan
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($startMenuPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
$Shortcut.WorkingDirectory = $installPath
$Shortcut.Description = "SubZero Studio - Your Personal AI Assistant"
$Shortcut.Save()

# Create Desktop shortcut
Write-Host "Creating Desktop shortcut..." -ForegroundColor Cyan
$DesktopShortcut = $WScriptShell.CreateShortcut($desktopPath)
$DesktopShortcut.TargetPath = "powershell.exe"
$DesktopShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
$DesktopShortcut.WorkingDirectory = $installPath
$DesktopShortcut.Description = "SubZero Studio - Your Personal AI Assistant"
$DesktopShortcut.Save()

# Create uninstaller
Write-Host "Creating uninstaller..." -ForegroundColor Cyan
$uninstallerPath = "$installPath\Uninstall.ps1"
$uninstallerScript = "Write-Host 'SubZero Studio Uninstaller' -ForegroundColor Red" + [Environment]::NewLine
$uninstallerScript += "Write-Host ''" + [Environment]::NewLine
$uninstallerScript += "`$response = Read-Host 'Remove SubZero Studio? (Y/N)'" + [Environment]::NewLine
$uninstallerScript += "if (`$response -eq 'Y' -or `$response -eq 'y') {" + [Environment]::NewLine
$uninstallerScript += "    Remove-Item -Path '$installPath' -Recurse -Force -ErrorAction SilentlyContinue" + [Environment]::NewLine
$uninstallerScript += "    Remove-Item -Path '$startMenuPath' -Force -ErrorAction SilentlyContinue" + [Environment]::NewLine
$uninstallerScript += "    Remove-Item -Path '$desktopPath' -Force -ErrorAction SilentlyContinue" + [Environment]::NewLine
$uninstallerScript += "    Write-Host 'Uninstalled!' -ForegroundColor Green" + [Environment]::NewLine
$uninstallerScript += "}" + [Environment]::NewLine
Set-Content -Path $uninstallerPath -Value $uninstallerScript

# Create version file
Write-Host "Creating version info..." -ForegroundColor Cyan
$versionInfo = @{
    Version = "1.0.0"
    InstallDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    InstallPath = $installPath
    DataPath = $userDataPath
}
$versionInfo | ConvertTo-Json | Set-Content "$installPath\version.json"

# Register in Windows (Add/Remove Programs)
Write-Host "Registering with Windows..." -ForegroundColor Cyan
$regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\SubZeroStudio"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "SubZero Studio"
Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "1.0.0"
Set-ItemProperty -Path $regPath -Name "Publisher" -Value "SubZero AI"
Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value $installPath
Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallerPath`""
Set-ItemProperty -Path $regPath -Name "DisplayIcon" -Value "powershell.exe"
Set-ItemProperty -Path $regPath -Name "NoModify" -Value 1
Set-ItemProperty -Path $regPath -Name "NoRepair" -Value 1

# Check Ollama
Write-Host ""
Write-Host "Checking Ollama installation..." -ForegroundColor Cyan
$ollamaCheck = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCheck) {
    Write-Host "  OK Ollama is installed" -ForegroundColor Green
}
else {
    Write-Host "  WARNING Ollama not found!" -ForegroundColor Red
    Write-Host "  Install from: https://ollama.ai" -ForegroundColor Yellow
}

# Complete
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "SubZero Studio is now installed!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Launch from:" -ForegroundColor Yellow
Write-Host "  - Start Menu (Search for SubZero Studio)" -ForegroundColor White
Write-Host "  - Desktop shortcut" -ForegroundColor White
Write-Host ""
Write-Host "Installation path: $installPath" -ForegroundColor Gray
Write-Host "Your data: $userDataPath" -ForegroundColor Gray
Write-Host ""
Write-Host "To uninstall: Settings > Apps > SubZero Studio" -ForegroundColor Yellow
Write-Host ""

$launch = Read-Host "Launch SubZero Studio now? (Y/N)"
if ($launch -eq "Y" -or $launch -eq "y") {
    Write-Host ""
    Write-Host "Starting SubZero Studio..." -ForegroundColor Cyan
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
    Start-Sleep -Seconds 2
    Write-Host "Studio is starting! Check your browser at http://localhost:8080" -ForegroundColor Green
}

Write-Host ""
Read-Host "Press Enter to close installer"
