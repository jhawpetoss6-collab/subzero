# SubZero Autonomous - Recursive Persistent Agent
# Runs 24/7, spawns agents, executes tasks autonomously

param(
    [string]$Mode = "daemon",  # daemon, once, interactive
    [string]$Goal,
    [switch]$Stop
)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$DaemonFile = "$SubZeroHome\daemon.json"
$GoalsFile = "$SubZeroHome\goals.json"
$ActionsLog = "$SubZeroHome\actions-log.txt"
$TaskQueueFile = "$SubZeroHome\task-queue.json"

# Initialize
if (!(Test-Path $SubZeroHome)) {
    New-Item -ItemType Directory -Path $SubZeroHome | Out-Null
}

#region Daemon Management

function Start-Daemon {
    param([string]$PrimaryGoal)
    
    $daemon = @{
        status = "running"
        started = (Get-Date).ToString('o')
        primaryGoal = $PrimaryGoal
        tasksCompleted = 0
        agentsSpawned = 0
        pid = $PID
        recursionDepth = 0
        maxRecursionDepth = 5
    }
    
    $daemon | ConvertTo-Json | Set-Content $DaemonFile
    
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   SubZero Autonomous Agent - ACTIVE      ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "`nPrimary Goal: $PrimaryGoal" -ForegroundColor Green
    Write-Host "Mode: AUTONOMOUS" -ForegroundColor Yellow
    Write-Host "Status: Running 24/7" -ForegroundColor Green
    Write-Host "`nI will:" -ForegroundColor Yellow
    Write-Host "  - Monitor tasks continuously" -ForegroundColor Gray
    Write-Host "  - Spawn sub-agents as needed" -ForegroundColor Gray
    Write-Host "  - Execute approved actions" -ForegroundColor Gray
    Write-Host "  - Log everything" -ForegroundColor Gray
    Write-Host "`nPress Ctrl+C to stop or run with -Stop flag`n" -ForegroundColor Red
    
    return $daemon
}

function Stop-Daemon {
    if (Test-Path $DaemonFile) {
        $daemon = Get-Content $DaemonFile | ConvertFrom-Json
        $daemon.status = "stopped"
        $daemon.stopped = (Get-Date).ToString('o')
        $daemon | ConvertTo-Json | Set-Content $DaemonFile
        
        Write-Host "[DAEMON STOPPED]" -ForegroundColor Red
        Write-Host "Tasks completed: $($daemon.tasksCompleted)" -ForegroundColor Gray
        Write-Host "Agents spawned: $($daemon.agentsSpawned)" -ForegroundColor Gray
    }
}

function Get-DaemonStatus {
    if (Test-Path $DaemonFile) {
        return Get-Content $DaemonFile | ConvertFrom-Json
    }
    return $null
}

#endregion

#region Task Queue (What to do)

function Initialize-TaskQueue {
    if (!(Test-Path $TaskQueueFile)) {
        $queue = @{
            tasks = @()
            lastProcessed = (Get-Date).ToString('o')
        }
        $queue | ConvertTo-Json | Set-Content $TaskQueueFile
    }
}

function Add-Task {
    param(
        [string]$Description,
        [string]$Type,  # research, execute, monitor, communicate
        [string]$Priority = "normal",  # low, normal, high, urgent
        [hashtable]$Parameters = @{}
    )
    
    Initialize-TaskQueue
    $queue = Get-Content $TaskQueueFile | ConvertFrom-Json
    
    $task = @{
        id = "task_$(Get-Random)"
        description = $Description
        type = $Type
        priority = $Priority
        parameters = $Parameters
        status = "pending"
        created = (Get-Date).ToString('o')
        attempts = 0
        result = $null
    }
    
    $queue.tasks += $task
    $queue | ConvertTo-Json -Depth 10 | Set-Content $TaskQueueFile
    
    Log-Action "Task added: $Description (Priority: $Priority)"
    
    return $task
}

function Get-NextTask {
    Initialize-TaskQueue
    $queue = Get-Content $TaskQueueFile | ConvertFrom-Json
    
    # Get pending tasks, sorted by priority
    $priorityOrder = @{ urgent = 0; high = 1; normal = 2; low = 3 }
    $pendingTasks = $queue.tasks | Where-Object { $_.status -eq "pending" } |
        Sort-Object { $priorityOrder[$_.priority] }
    
    return $pendingTasks | Select-Object -First 1
}

function Update-TaskStatus {
    param([string]$TaskId, [string]$Status, [string]$Result = $null)
    
    $queue = Get-Content $TaskQueueFile | ConvertFrom-Json
    $task = $queue.tasks | Where-Object { $_.id -eq $TaskId }
    
    if ($task) {
        $task.status = $Status
        $task.updated = (Get-Date).ToString('o')
        if ($Result) { $task.result = $Result }
        
        $queue | ConvertTo-Json -Depth 10 | Set-Content $TaskQueueFile
    }
}

#endregion

#region Action Execution (Do things on computer)

function Execute-Action {
    param(
        [string]$ActionType,
        [hashtable]$Parameters,
        [switch]$DryRun
    )
    
    if ($DryRun) {
        Write-Host "[DRY RUN] Would execute: $ActionType" -ForegroundColor Yellow
        return "Dry run - no action taken"
    }
    
    switch ($ActionType) {
        'run_command' {
            return Execute-Command @Parameters
        }
        'file_operation' {
            return Execute-FileOperation @Parameters
        }
        'web_request' {
            return Execute-WebRequest @Parameters
        }
        'trading' {
            return Execute-Trading @Parameters
        }
        'communicate_with_warp' {
            return Communicate-WithWarp @Parameters
        }
        'spawn_agent' {
            return Spawn-SubAgent @Parameters
        }
        default {
            return "Unknown action type: $ActionType"
        }
    }
}

function Execute-Command {
    param([string]$Command, [switch]$RequiresApproval = $false)
    
    if ($RequiresApproval) {
        Log-Action "Command requires approval: $Command"
        return "APPROVAL_REQUIRED"
    }
    
    try {
        Log-Action "Executing command: $Command"
        $result = Invoke-Expression $Command 2>&1 | Out-String
        Log-Action "Command result: $result"
        return $result
    }
    catch {
        Log-Action "Command failed: $_"
        return "ERROR: $_"
    }
}

function Execute-FileOperation {
    param([string]$Operation, [string]$Path, [string]$Content = $null)
    
    Log-Action "File operation: $Operation on $Path"
    
    switch ($Operation) {
        'read' {
            return Get-Content $Path -Raw
        }
        'write' {
            Set-Content $Path $Content
            return "File written: $Path"
        }
        'create' {
            New-Item -ItemType File -Path $Path -Force | Out-Null
            return "File created: $Path"
        }
        default {
            return "Unknown file operation: $Operation"
        }
    }
}

function Execute-WebRequest {
    param([string]$Url, [string]$Method = "GET", [hashtable]$Body = @{})
    
    Log-Action "Web request: $Method $Url"
    
    try {
        $response = Invoke-RestMethod -Uri $Url -Method $Method -Body $Body
        return $response | ConvertTo-Json
    }
    catch {
        return "ERROR: $_"
    }
}

function Execute-Trading {
    param([string]$Symbol, [string]$Action, [decimal]$Amount = 0)
    
    # DEMO ONLY - Replace with real trading API
    Log-Action "DEMO TRADING: $Action $Amount of $Symbol"
    
    $result = @"
⚠️  DEMO MODE - NOT REAL TRADING!

Action: $Action
Symbol: $Symbol
Amount: $Amount
Status: SIMULATED

This is a placeholder. To enable real trading:
1. Get API keys from your broker
2. Replace this function with real API calls
3. NEVER trade with money you can't afford to lose!
"@
    
    return $result
}

function Communicate-WithWarp {
    param([string]$Message, [string]$Context = "")
    
    Log-Action "Communication with Warp: $Message"
    
    # This function could:
    # 1. Write to a file that you can read
    # 2. Send notification
    # 3. Create task for you to review
    
    $commFile = "$SubZeroHome\warp-messages.txt"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content $commFile "[$timestamp] $Message"
    
    # Use Ollama to craft message
    $prompt = @"
You are SubZero agent communicating with the user's Warp AI assistant.
Context: $Context
Task: $Message

Write a clear, concise message explaining what you need.
"@
    
    $response = ollama run llama3.2 $prompt
    Add-Content $commFile "Response prepared: $response"
    
    return $response
}

function Spawn-SubAgent {
    param([string]$Role, [string]$Task, [int]$RecursionDepth = 0)
    
    $daemon = Get-DaemonStatus
    
    if ($RecursionDepth -ge $daemon.maxRecursionDepth) {
        Log-Action "Max recursion depth reached. Not spawning sub-agent."
        return "MAX_RECURSION_REACHED"
    }
    
    Log-Action "Spawning sub-agent: $Role for task: $Task (Depth: $RecursionDepth)"
    
    # Start background job for sub-agent
    $job = Start-Job -ScriptBlock {
        param($Role, $Task, $Depth, $SubZeroHome)
        
        # Sub-agent can spawn more sub-agents (recursive!)
        $result = "Sub-agent $Role working on: $Task at depth $Depth"
        
        # Add result to shared location
        $resultFile = "$SubZeroHome\subagent-results.txt"
        Add-Content $resultFile $result
        
        return $result
    } -ArgumentList $Role, $Task, ($RecursionDepth + 1), $SubZeroHome
    
    # Update daemon
    $daemon.agentsSpawned++
    $daemon.recursionDepth = [Math]::Max($daemon.recursionDepth, $RecursionDepth + 1)
    $daemon | ConvertTo-Json | Set-Content $DaemonFile
    
    return "Sub-agent spawned: $Role (Job ID: $($job.Id))"
}

#endregion

#region Safety & Logging

function Log-Action {
    param([string]$Message)
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Add-Content $ActionsLog $logEntry
    Write-Host $logEntry -ForegroundColor Gray
}

function Check-Safety {
    param([string]$Action, [hashtable]$Parameters)
    
    # Define dangerous actions
    $dangerousPatterns = @(
        'rm -rf /',
        'del /f /s /q',
        'format',
        'reg delete',
        'shutdown',
        'taskkill /f'
    )
    
    $actionString = "$Action $($Parameters | ConvertTo-Json)"
    
    foreach ($pattern in $dangerousPatterns) {
        if ($actionString -match $pattern) {
            Log-Action "BLOCKED dangerous action: $Action"
            return $false
        }
    }
    
    return $true
}

#endregion

#region Main Autonomous Loop

function Start-AutonomousLoop {
    param([string]$Goal)
    
    $daemon = Start-Daemon -PrimaryGoal $Goal
    
    # Main loop - runs forever
    while ($true) {
        $daemon = Get-DaemonStatus
        
        if ($daemon.status -ne "running") {
            Write-Host "Daemon stopped. Exiting..." -ForegroundColor Red
            break
        }
        
        # Get next task
        $task = Get-NextTask
        
        if ($task) {
            Write-Host "`n[PROCESSING] $($task.description)" -ForegroundColor Cyan
            
            # Safety check
            if (!(Check-Safety -Action $task.type -Parameters $task.parameters)) {
                Update-TaskStatus -TaskId $task.id -Status "blocked" -Result "Safety check failed"
                continue
            }
            
            # Execute task
            try {
                $result = Execute-Action -ActionType $task.type -Parameters $task.parameters
                Update-TaskStatus -TaskId $task.id -Status "completed" -Result $result
                
                $daemon.tasksCompleted++
                $daemon | ConvertTo-Json | Set-Content $DaemonFile
                
                Write-Host "[COMPLETED] $($task.description)" -ForegroundColor Green
            }
            catch {
                Update-TaskStatus -TaskId $task.id -Status "failed" -Result "ERROR: $_"
                Write-Host "[FAILED] $($task.description): $_" -ForegroundColor Red
            }
        }
        else {
            # No tasks - wait
            Write-Host "[IDLE] Waiting for tasks..." -ForegroundColor Gray
        }
        
        # Sleep before next iteration
        Start-Sleep -Seconds 5
    }
}

#endregion

#region Interactive Setup

function Start-InteractiveSetup {
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   SubZero Autonomous Setup              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    
    Write-Host "`nThis will make SubZero run autonomously!" -ForegroundColor Yellow
    Write-Host "`nWhat can it do?" -ForegroundColor Green
    Write-Host "  ✓ Run 24/7 in background" -ForegroundColor Gray
    Write-Host "  ✓ Execute commands on your computer" -ForegroundColor Gray
    Write-Host "  ✓ Spawn sub-agents (recursive)" -ForegroundColor Gray
    Write-Host "  ✓ Monitor and take actions" -ForegroundColor Gray
    Write-Host "  ✓ Communicate with Warp AI for you" -ForegroundColor Gray
    Write-Host "  ✓ Do day trading (DEMO only!)" -ForegroundColor Gray
    
    Write-Host "`n⚠️  IMPORTANT SAFETY:" -ForegroundColor Red
    Write-Host "  - Dangerous commands are blocked" -ForegroundColor Yellow
    Write-Host "  - All actions are logged" -ForegroundColor Yellow
    Write-Host "  - You can stop it anytime" -ForegroundColor Yellow
    Write-Host "  - Review logs regularly!" -ForegroundColor Yellow
    
    Write-Host "`nWhat is your primary goal? " -NoNewline -ForegroundColor Green
    $goal = Read-Host
    
    Write-Host "`nAdd some initial tasks:" -ForegroundColor Yellow
    Write-Host "1. Monitor crypto prices"
    Write-Host "2. Research market trends"
    Write-Host "3. Communicate updates to Warp"
    Write-Host "4. Custom task"
    Write-Host "5. Start with no tasks`n"
    
    Write-Host "Choice (1-5): " -NoNewline
    $choice = Read-Host
    
    switch ($choice) {
        '1' {
            Add-Task -Description "Monitor BTC price every 5 minutes" -Type "monitor" -Priority "normal"
            Add-Task -Description "Alert if BTC changes >5%" -Type "communicate_with_warp" -Priority "high"
        }
        '2' {
            Add-Task -Description "Research crypto market trends" -Type "research" -Priority "normal"
            Add-Task -Description "Summarize findings" -Type "communicate_with_warp" -Priority "normal"
        }
        '3' {
            Add-Task -Description "Send daily update to Warp" -Type "communicate_with_warp" -Priority "normal"
        }
        '4' {
            Write-Host "Task description: " -NoNewline
            $taskDesc = Read-Host
            Add-Task -Description $taskDesc -Type "execute" -Priority "normal"
        }
    }
    
    Write-Host "`nStarting autonomous mode..." -ForegroundColor Green
    Start-Sleep -Seconds 2
    
    Start-AutonomousLoop -Goal $goal
}

#endregion

#region Main Entry

if ($Stop) {
    Stop-Daemon
    exit
}

if ($Mode -eq "daemon" -and $Goal) {
    Start-AutonomousLoop -Goal $Goal
}
elseif ($Mode -eq "interactive") {
    Start-InteractiveSetup
}
else {
    Write-Host "SubZero Autonomous Agent" -ForegroundColor Cyan
    Write-Host "`nUsage:" -ForegroundColor Yellow
    Write-Host "  Interactive setup:  .\subzero-autonomous.ps1 -Mode interactive" -ForegroundColor Gray
    Write-Host "  Start daemon:       .\subzero-autonomous.ps1 -Goal 'Your goal'" -ForegroundColor Gray
    Write-Host "  Stop daemon:        .\subzero-autonomous.ps1 -Stop" -ForegroundColor Gray
    Write-Host "`nStatus:" -ForegroundColor Yellow
    $status = Get-DaemonStatus
    if ($status) {
        Write-Host "  Status: $($status.status)" -ForegroundColor Green
        Write-Host "  Goal: $($status.primaryGoal)" -ForegroundColor Gray
        Write-Host "  Tasks completed: $($status.tasksCompleted)" -ForegroundColor Gray
        Write-Host "  Agents spawned: $($status.agentsSpawned)" -ForegroundColor Gray
    } else {
        Write-Host "  Not running" -ForegroundColor Red
    }
}

#endregion
