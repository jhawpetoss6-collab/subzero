# ═══════════════════════════════════════════════════════════
# Spine Rip Bot Fix Installer
# ═══════════════════════════════════════════════════════════
# This script backs up your original bot and installs the 
# fixed version with improved error handling and connections.

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       SPINE RIP BOT - INSTALLING FIXES                   ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$originalFile = "sz_telegram.py"
$fixedFile = "sz_telegram_fixed.py"
$backupFile = "sz_telegram_backup.py"

# Check if files exist
if (-not (Test-Path $fixedFile)) {
    Write-Host "✗ ERROR: $fixedFile not found!" -ForegroundColor Red
    Write-Host "  Make sure you're in the subzero directory." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $originalFile)) {
    Write-Host "✗ WARNING: $originalFile not found!" -ForegroundColor Yellow
    Write-Host "  Creating new installation..." -ForegroundColor Yellow
    Copy-Item $fixedFile $originalFile
    Write-Host "✓ Installed fixed version as $originalFile" -ForegroundColor Green
    exit 0
}

# Show what will be done
Write-Host "This will:" -ForegroundColor White
Write-Host "  1. Backup $originalFile → $backupFile" -ForegroundColor Gray
Write-Host "  2. Replace $originalFile with fixed version" -ForegroundColor Gray
Write-Host ""

# Ask for confirmation
$response = Read-Host "Continue? (Y/N)"
if ($response -ne 'Y' -and $response -ne 'y') {
    Write-Host "✗ Installation cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# Step 1: Backup original
Write-Host "→ Backing up original file..." -ForegroundColor Cyan
try {
    Copy-Item $originalFile $backupFile -Force
    Write-Host "✓ Backup created: $backupFile" -ForegroundColor Green
} catch {
    Write-Host "✗ Backup failed: $_" -ForegroundColor Red
    exit 1
}

# Step 2: Install fixed version
Write-Host "→ Installing fixed version..." -ForegroundColor Cyan
try {
    Copy-Item $fixedFile $originalFile -Force
    Write-Host "✓ Fixed version installed!" -ForegroundColor Green
} catch {
    Write-Host "✗ Installation failed: $_" -ForegroundColor Red
    Write-Host "  Restoring backup..." -ForegroundColor Yellow
    Copy-Item $backupFile $originalFile -Force
    exit 1
}

# Success
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  INSTALLATION COMPLETE                    ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "✓ Bot fixes installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "WHAT'S NEW:" -ForegroundColor White
Write-Host "  • Auto-retry on connection failures (3 attempts)" -ForegroundColor Gray
Write-Host "  • Better timeout handling with helpful messages" -ForegroundColor Gray
Write-Host "  • Real-time connection health monitoring" -ForegroundColor Gray
Write-Host "  • Enhanced error messages with solutions" -ForegroundColor Gray
Write-Host "  • Improved logging and status command" -ForegroundColor Gray
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor White
Write-Host "  1. Restart the bot if it's running" -ForegroundColor Gray
Write-Host "  2. Test with: python sz_telegram.py" -ForegroundColor Gray
Write-Host "  3. Check status: Send /status to your bot" -ForegroundColor Gray
Write-Host ""
Write-Host "Need to revert? Run:" -ForegroundColor Yellow
Write-Host "  copy $backupFile $originalFile" -ForegroundColor Yellow
Write-Host ""
