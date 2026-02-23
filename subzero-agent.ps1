# SubZero Agent System v1.0
# Autonomous AI agent with tools to control your computer

param([switch]$Debug)

$AgentHome = "$env:USERPROFILE\.subzero\agent"
$ToolsDir = "$AgentHome\tools"
$ProjectsDir = "$AgentHome\projects"
$LogsDir = "$AgentHome\logs"
$MemoryFile = "$AgentHome\memory.json"

# Initialize
@($AgentHome, $ToolsDir, $ProjectsDir, $LogsDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Agent memory/learning
$memory = if (Test-Path $MemoryFile) {
    Get-Content $MemoryFile | ConvertFrom-Json
} else {
    @{
        tasks_completed = 0
        successful_actions = @()
        failed_actions = @()
        learned_patterns = @()
    }
}

# Tool definitions - what the agent can do
$tools = @{
    create_file = {
        param($path, $content)
        try {
            Set-Content -Path $path -Value $content -Force
            return @{ success = $true; message = "File created: $path" }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    edit_file = {
        param($path, $search, $replace)
        try {
            $content = Get-Content -Path $path -Raw
            $newContent = $content -replace [regex]::Escape($search), $replace
            Set-Content -Path $path -Value $newContent
            return @{ success = $true; message = "File edited: $path" }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    run_command = {
        param($command)
        try {
            $output = Invoke-Expression $command 2>&1 | Out-String
            return @{ success = $true; output = $output }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    run_python = {
        param($code)
        try {
            $tempFile = "$env:TEMP\subzero_temp.py"
            Set-Content -Path $tempFile -Value $code
            $output = python $tempFile 2>&1 | Out-String
            Remove-Item $tempFile -ErrorAction SilentlyContinue
            return @{ success = $true; output = $output }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    read_file = {
        param($path)
        try {
            $content = Get-Content -Path $path -Raw
            return @{ success = $true; content = $content }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    list_files = {
        param($path)
        try {
            $files = Get-ChildItem -Path $path | Select-Object Name, Length, LastWriteTime
            return @{ success = $true; files = $files }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    web_search = {
        param($query)
        try {
            # Simple web search using DuckDuckGo HTML
            $url = "https://html.duckduckgo.com/html/?q=$([uri]::EscapeDataString($query))"
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing
            return @{ success = $true; results = "Search completed" }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
}

function Write-AgentLog {
    param($message, $level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$level] $message"
    $logFile = "$LogsDir\agent_$(Get-Date -Format 'yyyy-MM-dd').log"
    Add-Content -Path $logFile -Value $logEntry
    if ($Debug) { Write-Host $logEntry -ForegroundColor $(if($level -eq "ERROR"){"Red"}else{"Gray"}) }
}

function Invoke-AgentThinking {
    param($userRequest, $context = "")
    
    $systemPrompt = @"
You are SubZero Agent, an autonomous AI assistant with tools to control the computer.

AVAILABLE TOOLS:
- create_file(path, content) - Create new files
- edit_file(path, search, replace) - Edit existing files
- run_command(command) - Execute PowerShell commands
- run_python(code) - Execute Python code
- read_file(path) - Read file contents
- list_files(path) - List directory contents
- web_search(query) - Search the web

IMPORTANT INSTRUCTIONS:
1. Think step-by-step about the task
2. Use tools to accomplish the goal
3. Test your solutions
4. Report results clearly
5. If something fails, try to fix it
6. Format tool calls as: TOOL[tool_name](arg1, arg2)

Example:
User: "Create a Python calculator"
Response:
I'll create a calculator program:
TOOL[create_file](calculator.py, "def add(a,b): return a+b...")
TOOL[run_python](calculator.py)
Done! Calculator created and tested.

$context

User request: $userRequest
"@

    Write-AgentLog "Thinking about: $userRequest"
    $response = ollama run qwen2.5:1.5b $systemPrompt 2>&1 | Out-String
    return $response
}

function Execute-ToolCalls {
    param($aiResponse)
    
    # Parse tool calls from AI response
    $toolPattern = 'TOOL\[([^\]]+)\]\(([^\)]+)\)'
    $matches = [regex]::Matches($aiResponse, $toolPattern)
    
    $results = @()
    foreach ($match in $matches) {
        $toolName = $match.Groups[1].Value
        $argsString = $match.Groups[2].Value
        
        # Parse arguments
        $args = $argsString -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") }
        
        Write-AgentLog "Executing tool: $toolName with args: $($args -join ', ')"
        
        if ($tools.ContainsKey($toolName)) {
            $result = & $tools[$toolName] @args
            $results += @{
                tool = $toolName
                args = $args
                result = $result
            }
            
            if ($result.success) {
                Write-AgentLog "Tool $toolName succeeded"
                $script:memory.successful_actions += @{
                    tool = $toolName
                    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                }
            } else {
                Write-AgentLog "Tool $toolName failed: $($result.error)" -level "ERROR"
                $script:memory.failed_actions += @{
                    tool = $toolName
                    error = $result.error
                    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                }
            }
        }
    }
    
    return $results
}

function Save-AgentMemory {
    $script:memory.tasks_completed++
    $script:memory | ConvertTo-Json -Depth 10 | Set-Content $MemoryFile
}

# Main Agent Loop
Clear-Host
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    SubZero Agent System v1.0" -ForegroundColor Cyan
Write-Host "    Autonomous AI with Computer Control" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "I can:" -ForegroundColor Yellow
Write-Host "  - Write and edit code" -ForegroundColor Gray
Write-Host "  - Create software projects" -ForegroundColor Gray
Write-Host "  - Run commands on your PC" -ForegroundColor Gray
Write-Host "  - Execute Python/PowerShell" -ForegroundColor Gray
Write-Host "  - Search the web" -ForegroundColor Gray
Write-Host "  - Learn from my actions" -ForegroundColor Gray
Write-Host ""
Write-Host "Tasks completed: $($memory.tasks_completed)" -ForegroundColor Green
Write-Host "Type 'exit' to quit, 'tools' to see available tools" -ForegroundColor Gray
Write-Host ""

while ($true) {
    Write-Host "You: " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    if ($userInput -eq "exit") {
        Save-AgentMemory
        Write-Host "`nGoodbye!" -ForegroundColor Yellow
        break
    }
    
    if ($userInput -eq "tools") {
        Write-Host "`nAvailable Tools:" -ForegroundColor Yellow
        $tools.Keys | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        Write-Host ""
        continue
    }
    
    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    
    Write-Host ""
    Write-Host "SubZero Agent: Thinking..." -ForegroundColor Green
    
    try {
        # Agent thinks about the task
        $aiResponse = Invoke-AgentThinking -userRequest $userInput
        
        Write-Host ""
        Write-Host "SubZero Agent:" -ForegroundColor Green
        Write-Host $aiResponse -ForegroundColor White
        
        # Execute any tool calls
        $toolResults = Execute-ToolCalls -aiResponse $aiResponse
        
        if ($toolResults.Count -gt 0) {
            Write-Host "`nTool Execution Results:" -ForegroundColor Yellow
            foreach ($result in $toolResults) {
                $status = if ($result.result.success) { "[OK]" } else { "[FAILED]" }
                $color = if ($result.result.success) { "Green" } else { "Red" }
                Write-Host "  $status $($result.tool)" -ForegroundColor $color
                if ($result.result.message) {
                    Write-Host "    $($result.result.message)" -ForegroundColor Gray
                }
                if ($result.result.output) {
                    Write-Host "    Output: $($result.result.output)" -ForegroundColor Gray
                }
            }
        }
        
        Save-AgentMemory
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}
