# SubZero Pro - AI Agent with Skills & Swarm
param(
    [string]$Message,
    [switch]$Interactive,
    [switch]$Telegram,
    [string]$Agent = "main"
)

$Model = "llama3.2"
$SubZeroHome = "$env:USERPROFILE\.subzero"
$MemoryDir = "$SubZeroHome\memory"
$SkillsDir = "$SubZeroHome\skills"
$AgentsDir = "$SubZeroHome\agents"

# Initialize directories
@($SubZeroHome, $MemoryDir, $SkillsDir, $AgentsDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ | Out-Null }
}

# Agent memory file
$AgentMemory = "$MemoryDir\$Agent.txt"

#region Skills System

function Get-AvailableSkills {
    $skills = @{
        'code' = @{
            name = 'Code Execution'
            description = 'Write and execute Python/PowerShell code'
            enabled = $true
        }
        'web' = @{
            name = 'Web Search'
            description = 'Search the web for information'
            enabled = $true
        }
        'telegram' = @{
            name = 'Telegram Bot'
            description = 'Send/receive messages via Telegram'
            enabled = $false  # Requires bot token
        }
        'trading' = @{
            name = 'Day Trading Analysis'
            description = 'Analyze stocks and crypto (DEMO ONLY - NOT REAL TRADING)'
            enabled = $true
        }
        'swarm' = @{
            name = 'Swarm Coordination'
            description = 'Spawn and coordinate multiple AI agents'
            enabled = $true
        }
    }
    return $skills
}

function Invoke-Skill {
    param(
        [string]$SkillName,
        [hashtable]$Parameters
    )
    
    switch ($SkillName) {
        'code' {
            return Execute-Code @Parameters
        }
        'web' {
            return Search-Web @Parameters
        }
        'telegram' {
            return Send-Telegram @Parameters
        }
        'trading' {
            return Analyze-Trading @Parameters
        }
        'swarm' {
            return Spawn-Agent @Parameters
        }
        default {
            return "Skill not found: $SkillName"
        }
    }
}

#endregion

#region Skill Implementations

function Execute-Code {
    param([string]$Code, [string]$Language = 'powershell')
    
    try {
        if ($Language -eq 'powershell') {
            $result = Invoke-Expression $Code 2>&1 | Out-String
            return $result
        }
        elseif ($Language -eq 'python') {
            $tempFile = "$env:TEMP\subzero_$(Get-Random).py"
            Set-Content $tempFile $Code
            $result = python $tempFile 2>&1
            Remove-Item $tempFile -ErrorAction SilentlyContinue
            return $result -join "`n"
        }
        else {
            return "Unsupported language: $Language"
        }
    }
    catch {
        return "Code execution error: $_"
    }
}

function Search-Web {
    param([string]$Query)
    
    try {
        $url = "https://duckduckgo.com/?q=$([uri]::EscapeDataString($Query))"
        Start-Process $url
        return "Opened web search for: $Query"
    }
    catch {
        return "Web search error: $_"
    }
}

function Send-Telegram {
    param([string]$Message, [string]$BotToken, [string]$ChatId)
    
    if (!$BotToken) {
        return "Telegram requires bot token. Set with: `$env:TELEGRAM_BOT_TOKEN"
    }
    
    try {
        $apiUrl = "https://api.telegram.org/bot$BotToken/sendMessage"
        $body = @{
            chat_id = $ChatId
            text = $Message
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $body -ContentType 'application/json'
        return "Message sent to Telegram"
    }
    catch {
        return "Telegram error: $_"
    }
}

function Analyze-Trading {
    param([string]$Symbol, [string]$Action = 'analyze')
    
    $warning = "⚠️  DEMO MODE - NOT REAL TRADING! This is for educational purposes only."
    
    try {
        # Simulate market data analysis
        $analysis = @"
$warning

📊 Analysis for $Symbol:
- Current Price: `$${Get-Random -Minimum 100 -Maximum 500}.${Get-Random -Minimum 10 -Maximum 99}
- 24h Change: $(if ((Get-Random -Minimum 0 -Maximum 2) -eq 1) { '+' } else { '-' })${Get-Random -Minimum 1 -Maximum 15}%
- Volume: $(Get-Random -Minimum 1 -Maximum 999)M
- Recommendation: $(('BUY', 'HOLD', 'SELL') | Get-Random)

⚠️  This is SIMULATED data. Do NOT use for real trading!
"@
        return $analysis
    }
    catch {
        return "Trading analysis error: $_"
    }
}

function Spawn-Agent {
    param([string]$AgentName, [string]$Role, [string]$Task)
    
    $agentFile = "$AgentsDir\$AgentName.json"
    
    $agentConfig = @{
        name = $AgentName
        role = $Role
        task = $Task
        status = 'active'
        created = (Get-Date).ToString('o')
        memory = "$MemoryDir\$AgentName.txt"
    }
    
    $agentConfig | ConvertTo-Json | Set-Content $agentFile
    
    return @"
🤖 Agent Spawned: $AgentName
Role: $Role
Task: $Task
Memory: $($agentConfig.memory)

Use: .\sz.ps1 -Agent $AgentName "your message"
"@
}

#endregion

#region Core Chat Function

function Chat {
    param([string]$UserMessage, [string]$AgentName = 'main')
    
    # Load context
    $context = ""
    $agentMemory = "$MemoryDir\$AgentName.txt"
    if (Test-Path $agentMemory) {
        $context = Get-Content $agentMemory -Tail 10 -Raw
    }
    
    # Check for skill invocations
    $skillPattern = '@skill\s+(\w+)\s*\{([^}]+)\}'
    if ($UserMessage -match $skillPattern) {
        $skillName = $matches[1]
        $skillParams = $matches[2]
        
        # Parse parameters (simple key=value format)
        $params = @{}
        $skillParams -split ';' | ForEach-Object {
            if ($_ -match '(\w+)=(.+)') {
                $params[$matches[1].Trim()] = $matches[2].Trim()
            }
        }
        
        Write-Host "`n🔧 Executing skill: $skillName" -ForegroundColor Yellow
        $skillResult = Invoke-Skill -SkillName $skillName -Parameters $params
        Write-Host $skillResult -ForegroundColor Cyan
        
        Add-Content $agentMemory "`nYou: $UserMessage`nSkill Result: $skillResult"
        return $skillResult
    }
    
    # Normal chat
    $systemPrompt = @"
You are SubZero, an AI agent with special abilities:
- Code execution: Ask me to run code
- Web search: Ask me to search for information
- Trading analysis: Ask me to analyze stocks/crypto (demo only)
- Swarm: Ask me to spawn helper agents

Current agent: $AgentName
"@
    
    $prompt = "$systemPrompt`n`n$context`nYou: $UserMessage`nAssistant:"
    
    Add-Content $agentMemory "`nYou: $UserMessage"
    
    Write-Host "`n🤖 SubZero: " -NoNewline -ForegroundColor Cyan
    $response = ollama run $Model $prompt
    
    Add-Content $agentMemory "Assistant: $response"
    
    return $response
}

#endregion

#region Main Entry Point

if ($Message) {
    # Single message mode
    Chat -UserMessage $Message -AgentName $Agent
}
else {
    # Interactive mode
    Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║      SubZero Pro - Agent Swarm       ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "Agent: $Agent | Model: $Model`n" -ForegroundColor Gray
    
    # Show available skills
    Write-Host "Available Skills:" -ForegroundColor Yellow
    Get-AvailableSkills.GetEnumerator() | ForEach-Object {
        $status = if ($_.Value.enabled) { "✓" } else { "✗" }
        Write-Host "  $status $($_.Key): $($_.Value.description)" -ForegroundColor Gray
    }
    
    Write-Host "`nCommands:" -ForegroundColor Yellow
    Write-Host "  exit - Quit" -ForegroundColor Gray
    Write-Host "  skills - List skills" -ForegroundColor Gray
    Write-Host "  agents - List spawned agents" -ForegroundColor Gray
    Write-Host "  @skill <name> {params} - Use a skill`n" -ForegroundColor Gray
    
    while ($true) {
        Write-Host "You: " -NoNewline -ForegroundColor Green
        $userInput = Read-Host
        
        if ($userInput -eq 'exit') {
            Write-Host "❄️  Goodbye!" -ForegroundColor Cyan
            break
        }
        
        if ($userInput -eq 'skills') {
            Get-AvailableSkills.GetEnumerator() | ForEach-Object {
                Write-Host "  • $($_.Key): $($_.Value.description)" -ForegroundColor Cyan
            }
            continue
        }
        
        if ($userInput -eq 'agents') {
            $agents = Get-ChildItem "$AgentsDir\*.json" -ErrorAction SilentlyContinue
            if ($agents) {
                $agents | ForEach-Object {
                    $config = Get-Content $_.FullName | ConvertFrom-Json
                    Write-Host "  🤖 $($config.name): $($config.role)" -ForegroundColor Cyan
                }
            } else {
                Write-Host "  No agents spawned yet" -ForegroundColor Gray
            }
            continue
        }
        
        if ($userInput) {
            Chat -UserMessage $userInput -AgentName $Agent
        }
    }
}

#endregion
