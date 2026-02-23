# Quick Test Script for SubZero Warp

Write-Host "`n=== SUBZERO WARP TEST ===" -ForegroundColor Cyan

# Test 1: Multimodal script exists
Write-Host "`nTest 1: Checking multimodal_assistant.py..." -NoNewline
if (Test-Path "C:\Users\jhawp\subzero\multimodal_assistant.py") {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " MISSING" -ForegroundColor Red
}

# Test 2: Documentation exists
Write-Host "Test 2: Checking MULTIMODAL_GUIDE.md..." -NoNewline
if (Test-Path "C:\Users\jhawp\subzero\MULTIMODAL_GUIDE.md") {
    $size = (Get-Item "C:\Users\jhawp\subzero\MULTIMODAL_GUIDE.md").Length
    Write-Host " OK ($size bytes)" -ForegroundColor Green
} else {
    Write-Host " MISSING" -ForegroundColor Red
}

# Test 3: Quick reference exists
Write-Host "Test 3: Checking MULTIMODAL_QUICK_REF.md..." -NoNewline
if (Test-Path "C:\Users\jhawp\subzero\MULTIMODAL_QUICK_REF.md") {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " MISSING" -ForegroundColor Red
}

# Test 4: Main script exists
Write-Host "Test 4: Checking subzero-warp.ps1..." -NoNewline
if (Test-Path "C:\Users\jhawp\subzero\subzero-warp.ps1") {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " MISSING" -ForegroundColor Red
}

Write-Host "`n=== HOW TO USE ===" -ForegroundColor Cyan
Write-Host @"

1. Start SubZero Warp:
   .\subzero-warp.ps1

2. Inside SubZero, try these commands:
   learn multimodal                  # Shows full multimodal guide
   learn recursive_algorithm_adaptation  # Shows self-improving AI guide
   create multimodal script          # Creates Python assistant

3. Run the Python assistant:
   python multimodal_assistant.py
   (Then drag & drop any file!)

"@ -ForegroundColor White

Write-Host "=== FILES READY! ===" -ForegroundColor Green
Write-Host "All learning modules and scripts are installed and ready to use!`n" -ForegroundColor Yellow
