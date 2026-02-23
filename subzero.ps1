# SubZero - Lightweight AI Agent (PowerShell)
# Uses Ollama locally with conversation memory

$script:SubZeroHome = "$env:USERPROFILE\.subzero"
$script:MemoryFile = "$SubZeroHome\memory.json"
$script:Model = "llama3.2"

function Initialize-SubZero {
    if (-not (Test-Path $SubZeroHome)) {
        New-Item -ItemType Directory -Path $SubZeroHome -Force | Out-Null
    }
    
    if (Test-Path $MemoryFile) {
        $script:Conversation = Get-Content $MemoryFile | ConvertFrom-Json
    } else {
        $script:Conversation = @()
    }
}

function Save-Memory {
    $script:Conversation | Select-Object -Last 50 | ConvertTo-Json -Depth 10 | Set-Content $MemoryFile
}

function Invoke-Ollama {
    param([string]$Prompt)
    
    try {
        # Build context from last 10 messages
        $context = ($script:Conversation | Select-Object -Last 10 | ForEach-Object {
            $roleName = if ($_.role -eq 'user') { 'User' } else { 'Assistant' }
            "${roleName}: $($_.content)"
        }) -join "`n"
        
        $fullPrompt = "$context`nUser: $Prompt`nAssistant:"
        
        # Call Ollama
        $response = ollama run $Model $fullPrompt 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            return $response -join "`n"
        } else {
            return "Error: Unable to get response from Ollama"
        }
    }
    catch {
        return "Error: $_"
    }
}

function Send-Message {
    param([string]$UserInput)
    
    # Add user message
    $script:Conversation += @{
        role = 'user'
        content = $UserInput
        timestamp = (Get-Date).ToString('o')
    }
    
    # Get AI response
    $response = Invoke-Ollama -Prompt $UserInput
    
    # Add assistant response
    $script:Conversation += @{
        role = 'assistant'
        content = $response
        timestamp = (Get-Date).ToString('o')
    }
    
    # Save memory
    Save-Memory
    
    return $response
}

function Start-SubZeroInteractive {
    Write-Host "╔════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║         SubZero Agent v1.0         ║" -ForegroundColor Cyan
    Write-Host "║    Lightweight • Local • Free      ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "`nUsing model: $Model" -ForegroundColor Gray
    Write-Host "Type 'exit' to quit, 'clear' to clear memory`n" -ForegroundColor Gray
    
    while ($true) {
        Write-Host "`n🧊 You: " -NoNewline -ForegroundColor Green
        $input = Read-Host
        
        if ([string]::IsNullOrWhiteSpace($input)) {
            continue
        }
        
        if ($input -eq 'exit') {
            Write-Host "`n❄️  SubZero shutting down..." -ForegroundColor Cyan
            break
        }
        
        if ($input -eq 'clear') {
            $script:Conversation = @()
            Save-Memory
            Write-Host "💭 Memory cleared!" -ForegroundColor Yellow
            continue
        }
        
        Write-Host "`n🤖 SubZero: " -NoNewline -ForegroundColor Blue
        $response = Send-Message -UserInput $input
        Write-Host $response -ForegroundColor White
    }
}

# Main entry point
Initialize-SubZero

if ($args.Count -gt 0) {
    # Single message mode
    $message = $args -join ' '
    $response = Send-Message -UserInput $message
    Write-Host $response
} else {
    # Interactive mode
    Start-SubZeroInteractive
}
