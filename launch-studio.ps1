# SubZero Studio + Mini-Warp
# Integrated AI assistant that acts like Warp AI but runs locally

param([int]$Port = 8080)

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   SubZero Studio + Mini-Warp AI         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`nYour personal AI assistant - Just text naturally!" -ForegroundColor Green
Write-Host "Mini-Warp will:" -ForegroundColor Yellow
Write-Host "  ✓ Write code for you" -ForegroundColor Gray
Write-Host "  ✓ Edit files automatically" -ForegroundColor Gray
Write-Host "  ✓ Create audiobooks" -ForegroundColor Gray
Write-Host "  ✓ Process complex tasks" -ForegroundColor Gray
Write-Host "  ✓ Do the heavy lifting!" -ForegroundColor Gray
Write-Host "`nStarting..." -ForegroundColor Green
Start-Sleep -Seconds 2

$SubZeroHome = "$env:USERPROFILE\.subzero"
$StudioDir = "$SubZeroHome\studio"

# Enhanced AI Prompt - Makes Ollama act like Warp AI
$systemPrompt = @"
You are Mini-Warp, a helpful AI assistant integrated into SubZero Studio.

YOUR PERSONALITY:
- Friendly, direct, and action-oriented (like Warp AI)
- You DO THINGS, not just explain
- You write code, edit files, create content
- You're concise but thorough
- You use emojis occasionally 😊

YOUR CAPABILITIES:
- Write and edit code in any language
- Create book chapters and content
- Generate audiobook scripts
- Execute commands and tasks
- Help with projects and workflows

WHEN USER ASKS YOU TO DO SOMETHING:
1. Acknowledge what they want
2. DO IT (don't just explain how)
3. Show the result
4. Ask if they want anything else

EXAMPLES:
User: "Write chapter 3 of my sci-fi book"
You: "On it! Here's Chapter 3... [write full chapter] Done! Want me to convert it to audio?"

User: "Fix this Python bug"
You: "Found it! The issue is... [explain briefly] Fixed! [show corrected code]"

User: "Make me a trading bot"
You: "Building a trading bot for you... [create code] Here's your bot! Test it with: python bot.py"

BE PROACTIVE: If you can do something, DO IT. Don't wait for permission.
BE HELPFUL: Anticipate what they might need next.
BE FAST: Keep responses focused and actionable.
"@

# Save system prompt
$systemPrompt | Set-Content "$SubZeroHome\mini-warp-prompt.txt"

# Enhanced HTML with Mini-Warp integration
$html = Get-Content "C:\Users\jhawp\subzero\subzero-studio.ps1" -Raw
$html = $html -replace '<!DOCTYPE html>', @"
<!DOCTYPE html>
<!-- SubZero Studio + Mini-Warp AI -->
"@

# Launch SubZero Studio with Mini-Warp enhancements
Write-Host "Launching SubZero Studio with Mini-Warp AI..." -ForegroundColor Cyan
Write-Host "URL: http://localhost:$Port" -ForegroundColor Green
Write-Host "`nJust text naturally - Mini-Warp will handle everything!" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Red

# Start the enhanced studio
& "C:\Users\jhawp\subzero\subzero-studio.ps1" -Port $Port
