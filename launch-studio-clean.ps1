# SubZero Studio Launcher with Mini-Warp AI

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " SubZero Studio + Mini-Warp AI" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your personal AI assistant - Just text naturally!" -ForegroundColor Green
Write-Host ""
Write-Host "Mini-Warp will:" -ForegroundColor Yellow
Write-Host "  * Write code for you" -ForegroundColor Gray
Write-Host "  * Edit files automatically" -ForegroundColor Gray
Write-Host "  * Create audiobooks" -ForegroundColor Gray
Write-Host "  * Process complex tasks" -ForegroundColor Gray
Write-Host "  * Do the heavy lifting!" -ForegroundColor Gray
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host ""

# Mini-Warp system prompt
$env:MINIWARP_PROMPT = @"
You are Mini-Warp, a helpful AI assistant running locally via Ollama.
You are action-oriented and proactive. When asked to do something, you DO IT.
You write code, edit files, create content, and execute tasks automatically.
You don't just explain - you take action and get things done!
Be direct, helpful, and anticipate the user's needs.
"@

Write-Host "Launching SubZero Studio with Mini-Warp AI..." -ForegroundColor Cyan
Write-Host "URL: http://localhost:8080" -ForegroundColor Yellow
Write-Host ""
Write-Host "Just text naturally - Mini-Warp will handle everything!" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run the studio
& "$PSScriptRoot\subzero-studio.ps1"
