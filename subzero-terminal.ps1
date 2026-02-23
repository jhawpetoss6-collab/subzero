# SubZero Terminal Edition
# Pure terminal chat - no special characters

param()

$SubZeroHome = "$env:USERPROFILE\.subzero"
if (!(Test-Path $SubZeroHome)) { 
    New-Item -ItemType Directory -Path $SubZeroHome -Force | Out-Null 
}

# Header
Clear-Host
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "      SubZero AI - Terminal Edition" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  exit   - Quit" -ForegroundColor Gray
Write-Host "  clear  - Clear screen" -ForegroundColor Gray
Write-Host ""

# Main loop
while ($true) {
    Write-Host "You: " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    if ($userInput -eq "exit" -or $userInput -eq "quit") {
        Write-Host ""
        Write-Host "Goodbye!" -ForegroundColor Yellow
        break
    }
    
    if ($userInput -eq "clear") {
        Clear-Host
        Write-Host ""
        Write-Host "SubZero AI - Terminal" -ForegroundColor Cyan
        Write-Host ""
        continue
    }
    
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        continue
    }
    
    Write-Host ""
    Write-Host "SubZero is thinking..." -ForegroundColor DarkGray
    
    try {
        $systemPrompt = "You are SubZero, a helpful AI assistant. Be concise and practical."
        $fullPrompt = "$systemPrompt User asks: $userInput"
        
        $response = & ollama run llama3.2 $fullPrompt 2>&1 | Out-String
        
        Write-Host ""
        Write-Host "SubZero:" -ForegroundColor Green
        Write-Host $response.Trim() -ForegroundColor White
        Write-Host ""
        
    } catch {
        Write-Host ""
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
    }
}
