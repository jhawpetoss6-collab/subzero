# SubZero - Simple Terminal

Clear-Host
Write-Host "SubZero AI Terminal" -ForegroundColor Cyan
Write-Host "Type 'exit' to quit" -ForegroundColor Gray
Write-Host ""

while ($true) {
    Write-Host "You: " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    # Check exit FIRST before doing anything
    if ($userInput -eq "exit" -or $userInput -eq "quit") { 
        Write-Host ""
        Write-Host "Goodbye!" -ForegroundColor Yellow
        break
    }
    
    # Skip empty input
    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    
    Write-Host ""
    Write-Host "SubZero: " -ForegroundColor Green
    
    try {
        $response = & ollama run llama3.2 $userInput 2>&1 | Out-String
        Write-Host $response.Trim()
    } catch {
        Write-Host "Error: Could not connect to Ollama" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "Press any key to close..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
