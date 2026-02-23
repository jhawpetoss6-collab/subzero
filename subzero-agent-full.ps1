# SubZero Agent System v2.0 - Full Trading & Task Management
# Autonomous AI with day trading, task management, and algorithmic alerts

param([switch]$Debug)

$AgentHome = "$env:USERPROFILE\.subzero\agent"
$ToolsDir = "$AgentHome\tools"
$ProjectsDir = "$AgentHome\projects"
$LogsDir = "$AgentHome\logs"
$TradingDir = "$AgentHome\trading"
$TasksDir = "$AgentHome\tasks"
$MemoryFile = "$AgentHome\memory.json"
$TasksFile = "$TasksDir\tasks.json"
$TradesFile = "$TradingDir\trades.json"
$WatchlistFile = "$TradingDir\watchlist.json"
$AlertsFile = "$TradingDir\alerts.json"

# Initialize
@($AgentHome, $ToolsDir, $ProjectsDir, $LogsDir, $TradingDir, $TasksDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Load persistent data
$memory = if (Test-Path $MemoryFile) { Get-Content $MemoryFile | ConvertFrom-Json } else {
    @{ tasks_completed = 0; successful_actions = @(); failed_actions = @(); learned_patterns = @() }
}

$tasks = if (Test-Path $TasksFile) { Get-Content $TasksFile | ConvertFrom-Json } else { @() }
$trades = if (Test-Path $TradesFile) { Get-Content $TradesFile | ConvertFrom-Json } else { @() }
$watchlist = if (Test-Path $WatchlistFile) { Get-Content $WatchlistFile | ConvertFrom-Json } else { @() }
$alerts = if (Test-Path $AlertsFile) { Get-Content $AlertsFile | ConvertFrom-Json } else { @() }

# Market data API (Free - no API key needed for basic data)
function Get-StockPrice {
    param($symbol)
    try {
        # Using Yahoo Finance API (free, no key needed)
        $url = "https://query1.finance.yahoo.com/v8/finance/chart/$symbol"
        $response = Invoke-RestMethod -Uri $url -Method Get
        $price = $response.chart.result[0].meta.regularMarketPrice
        $change = $response.chart.result[0].meta.regularMarketChangePercent
        return @{
            success = $true
            symbol = $symbol
            price = [math]::Round($price, 2)
            change = [math]::Round($change, 2)
            timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        }
    } catch {
        return @{ success = $false; error = "Could not fetch price for $symbol" }
    }
}

# Tool definitions
$tools = @{
    # File operations
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
    
    read_file = {
        param($path)
        try {
            $content = Get-Content -Path $path -Raw
            return @{ success = $true; content = $content }
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
    
    # Task Management
    add_task = {
        param($title, $priority = "medium", $deadline = "")
        $task = @{
            id = [guid]::NewGuid().ToString()
            title = $title
            priority = $priority
            deadline = $deadline
            status = "pending"
            created = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        }
        $script:tasks += $task
        $script:tasks | ConvertTo-Json -Depth 10 | Set-Content $TasksFile
        return @{ success = $true; message = "Task added: $title"; task = $task }
    }
    
    list_tasks = {
        param($status = "all")
        $filtered = if ($status -eq "all") { $script:tasks } else { $script:tasks | Where-Object { $_.status -eq $status } }
        return @{ success = $true; tasks = $filtered; count = $filtered.Count }
    }
    
    complete_task = {
        param($taskId)
        $task = $script:tasks | Where-Object { $_.id -eq $taskId }
        if ($task) {
            $task.status = "completed"
            $task.completed = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            $script:tasks | ConvertTo-Json -Depth 10 | Set-Content $TasksFile
            return @{ success = $true; message = "Task completed: $($task.title)" }
        }
        return @{ success = $false; error = "Task not found" }
    }
    
    # Day Trading Functions
    get_price = {
        param($symbol)
        $data = Get-StockPrice -symbol $symbol.ToUpper()
        if ($data.success) {
            return @{ 
                success = $true
                message = "$($data.symbol): $$$($data.price) ($($data.change)%)"
                data = $data
            }
        }
        return $data
    }
    
    add_to_watchlist = {
        param($symbol, $targetPrice = 0, $stopLoss = 0)
        $item = @{
            symbol = $symbol.ToUpper()
            targetPrice = [double]$targetPrice
            stopLoss = [double]$stopLoss
            added = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        }
        $script:watchlist += $item
        $script:watchlist | ConvertTo-Json -Depth 10 | Set-Content $WatchlistFile
        return @{ success = $true; message = "Added $symbol to watchlist" }
    }
    
    check_watchlist = {
        $results = @()
        foreach ($item in $script:watchlist) {
            $priceData = Get-StockPrice -symbol $item.symbol
            if ($priceData.success) {
                $alert = $null
                if ($item.targetPrice -gt 0 -and $priceData.price -ge $item.targetPrice) {
                    $alert = "TARGET HIT"
                }
                if ($item.stopLoss -gt 0 -and $priceData.price -le $item.stopLoss) {
                    $alert = "STOP LOSS"
                }
                $results += @{
                    symbol = $item.symbol
                    price = $priceData.price
                    change = $priceData.change
                    alert = $alert
                    targetPrice = $item.targetPrice
                    stopLoss = $item.stopLoss
                }
            }
        }
        return @{ success = $true; watchlist = $results }
    }
    
    simulate_trade = {
        param($action, $symbol, $quantity, $price = 0)
        # DEMO ONLY - not real trading!
        $symbol = $symbol.ToUpper()
        $priceData = if ($price -eq 0) { Get-StockPrice -symbol $symbol } else { @{ success = $true; price = $price } }
        
        if ($priceData.success) {
            $trade = @{
                id = [guid]::NewGuid().ToString()
                action = $action
                symbol = $symbol
                quantity = [int]$quantity
                price = $priceData.price
                total = $priceData.price * [int]$quantity
                timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                mode = "SIMULATION"
            }
            $script:trades += $trade
            $script:trades | ConvertTo-Json -Depth 10 | Set-Content $TradesFile
            return @{ 
                success = $true
                message = "SIMULATED $action: $quantity shares of $symbol at $$$($priceData.price) = $$$($trade.total)"
                trade = $trade
            }
        }
        return @{ success = $false; error = "Could not get price" }
    }
    
    view_trades = {
        return @{ success = $true; trades = $script:trades; totalTrades = $script:trades.Count }
    }
    
    # Algorithmic Alerts
    create_alert = {
        param($symbol, $condition, $threshold)
        # Condition: "above", "below", "change_up", "change_down"
        $alert = @{
            id = [guid]::NewGuid().ToString()
            symbol = $symbol.ToUpper()
            condition = $condition
            threshold = [double]$threshold
            active = $true
            created = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        }
        $script:alerts += $alert
        $script:alerts | ConvertTo-Json -Depth 10 | Set-Content $AlertsFile
        return @{ success = $true; message = "Alert created for $symbol" }
    }
    
    check_alerts = {
        $triggered = @()
        foreach ($alert in ($script:alerts | Where-Object { $_.active })) {
            $priceData = Get-StockPrice -symbol $alert.symbol
            if ($priceData.success) {
                $trigger = $false
                switch ($alert.condition) {
                    "above" { $trigger = $priceData.price -gt $alert.threshold }
                    "below" { $trigger = $priceData.price -lt $alert.threshold }
                    "change_up" { $trigger = $priceData.change -gt $alert.threshold }
                    "change_down" { $trigger = $priceData.change -lt $alert.threshold }
                }
                if ($trigger) {
                    $triggered += @{
                        alert = $alert
                        currentPrice = $priceData.price
                        change = $priceData.change
                        message = "$($alert.symbol) triggered: $($alert.condition) $($alert.threshold)"
                    }
                    $alert.active = $false
                    $script:alerts | ConvertTo-Json -Depth 10 | Set-Content $AlertsFile
                }
            }
        }
        return @{ success = $true; triggered = $triggered; count = $triggered.Count }
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
    param($userRequest)
    
    $systemPrompt = @"
You are SubZero Agent v2.0, an autonomous AI with full computer control, day trading, and task management.

AVAILABLE TOOLS:

FILE OPERATIONS:
- create_file(path, content)
- edit_file(path, search, replace)
- read_file(path)
- run_command(command)
- run_python(code)

TASK MANAGEMENT:
- add_task(title, priority, deadline)
- list_tasks(status)
- complete_task(taskId)

DAY TRADING:
- get_price(symbol)
- add_to_watchlist(symbol, targetPrice, stopLoss)
- check_watchlist()
- simulate_trade(action, symbol, quantity, price)
- view_trades()

ALGORITHMIC ALERTS:
- create_alert(symbol, condition, threshold)
- check_alerts()

INSTRUCTIONS:
1. Think step-by-step
2. Use tools to accomplish tasks
3. For trading: Always check prices first, use simulation mode
4. Format tool calls as: TOOL[tool_name](arg1, arg2)
5. Be proactive and helpful

Example:
User: "Check AAPL stock and buy if under 150"
Response:
I'll check Apple stock price:
TOOL[get_price](AAPL)
Based on the price, I'll execute a simulated trade:
TOOL[simulate_trade](BUY, AAPL, 10, 0)

User request: $userRequest
"@

    Write-AgentLog "Processing: $userRequest"
    $response = ollama run qwen2.5:1.5b $systemPrompt 2>&1 | Out-String
    return $response
}

function Execute-ToolCalls {
    param($aiResponse)
    
    $toolPattern = 'TOOL\[([^\]]+)\]\(([^\)]*)\)'
    $matches = [regex]::Matches($aiResponse, $toolPattern)
    
    $results = @()
    foreach ($match in $matches) {
        $toolName = $match.Groups[1].Value
        $argsString = $match.Groups[2].Value
        
        $args = if ($argsString) {
            $argsString -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") }
        } else {
            @()
        }
        
        Write-AgentLog "Executing: $toolName($($args -join ', '))"
        
        if ($tools.ContainsKey($toolName)) {
            $result = & $tools[$toolName] @args
            $results += @{ tool = $toolName; args = $args; result = $result }
            
            if ($result.success) {
                Write-AgentLog "Success: $toolName"
                $script:memory.successful_actions += @{ tool = $toolName; timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss" }
            } else {
                Write-AgentLog "Failed: $toolName - $($result.error)" -level "ERROR"
                $script:memory.failed_actions += @{ tool = $toolName; error = $result.error; timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss" }
            }
        }
    }
    
    return $results
}

function Save-AgentData {
    $script:memory.tasks_completed++
    $script:memory | ConvertTo-Json -Depth 10 | Set-Content $MemoryFile
}

# Main Loop
Clear-Host
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "    SubZero Agent v2.0 - Full Trading System" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "CAPABILITIES:" -ForegroundColor Yellow
Write-Host "  Code & Software:  Create, edit, execute code" -ForegroundColor Gray
Write-Host "  Task Management:  Add, track, complete tasks" -ForegroundColor Gray
Write-Host "  Day Trading:      Price checks, simulated trades" -ForegroundColor Gray
Write-Host "  Watchlist:        Monitor stocks with alerts" -ForegroundColor Gray
Write-Host "  Algo Alerts:      Price & change notifications" -ForegroundColor Gray
Write-Host ""
Write-Host "STATS:" -ForegroundColor Yellow
Write-Host "  Tasks Completed:  $($memory.tasks_completed)" -ForegroundColor Green
Write-Host "  Active Tasks:     $(($tasks | Where-Object {$_.status -eq 'pending'}).Count)" -ForegroundColor Green
Write-Host "  Total Trades:     $($trades.Count) (SIMULATION)" -ForegroundColor Green
Write-Host "  Watchlist:        $($watchlist.Count) symbols" -ForegroundColor Green
Write-Host "  Active Alerts:    $(($alerts | Where-Object {$_.active}).Count)" -ForegroundColor Green
Write-Host ""
Write-Host "Commands: 'exit', 'tools', 'status', 'watchlist', 'tasks'" -ForegroundColor Gray
Write-Host ""

while ($true) {
    Write-Host "You: " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    if ($userInput -eq "exit") {
        Save-AgentData
        Write-Host "`nGoodbye!" -ForegroundColor Yellow
        break
    }
    
    if ($userInput -eq "tools") {
        Write-Host "`nAvailable Tools:" -ForegroundColor Yellow
        $tools.Keys | Sort-Object | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "status") {
        Write-Host "`nSystem Status:" -ForegroundColor Yellow
        Write-Host "  Tasks: $(($tasks | Where-Object {$_.status -eq 'pending'}).Count) pending" -ForegroundColor Gray
        Write-Host "  Trades: $($trades.Count) total" -ForegroundColor Gray
        Write-Host "  Watchlist: $($watchlist.Count) symbols" -ForegroundColor Gray
        Write-Host "  Alerts: $(($alerts | Where-Object {$_.active}).Count) active" -ForegroundColor Gray
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "watchlist") {
        Write-Host "`nChecking watchlist..." -ForegroundColor Yellow
        $result = & $tools['check_watchlist']
        foreach ($item in $result.watchlist) {
            $color = if ($item.alert) { "Red" } else { "Green" }
            $alertText = if ($item.alert) { " [$($item.alert)]" } else { "" }
            Write-Host "  $($item.symbol): $$$($item.price) ($($item.change)%)$alertText" -ForegroundColor $color
        }
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "tasks") {
        Write-Host "`nYour Tasks:" -ForegroundColor Yellow
        $pending = $tasks | Where-Object { $_.status -eq "pending" }
        if ($pending.Count -eq 0) {
            Write-Host "  No pending tasks" -ForegroundColor Gray
        } else {
            foreach ($task in $pending) {
                Write-Host "  [$($task.priority)] $($task.title)" -ForegroundColor Gray
            }
        }
        Write-Host ""
        continue
    }
    
    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    
    Write-Host ""
    Write-Host "SubZero Agent: Thinking..." -ForegroundColor Green
    
    try {
        $aiResponse = Invoke-AgentThinking -userRequest $userInput
        
        Write-Host ""
        Write-Host "SubZero Agent:" -ForegroundColor Green
        Write-Host $aiResponse -ForegroundColor White
        
        $toolResults = Execute-ToolCalls -aiResponse $aiResponse
        
        if ($toolResults.Count -gt 0) {
            Write-Host "`nActions Taken:" -ForegroundColor Yellow
            foreach ($result in $toolResults) {
                $status = if ($result.result.success) { "[OK]" } else { "[FAIL]" }
                $color = if ($result.result.success) { "Green" } else { "Red" }
                Write-Host "  $status $($result.tool)" -ForegroundColor $color
                if ($result.result.message) {
                    Write-Host "    $($result.result.message)" -ForegroundColor Gray
                }
                if ($result.result.output) {
                    Write-Host "    $($result.result.output)" -ForegroundColor Gray
                }
            }
        }
        
        Save-AgentData
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}
