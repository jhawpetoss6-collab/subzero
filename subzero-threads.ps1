# SubZero - Thread-Split Architecture
# Front-End (fast) + Back-End (deep) + Watchdog (autonomous)

param(
    [string]$Message,
    [string]$Mode = "normal",  # normal, thinking, watchdog
    [string]$Agent = "main"
)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$ThreadsDir = "$SubZeroHome\threads"
$TasksDir = "$SubZeroHome\tasks"
$WatchdogFile = "$SubZeroHome\watchdog.json"

# Initialize
@($SubZeroHome, $ThreadsDir, $TasksDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ | Out-Null }
}

#region Thread Management

function Start-BackendThread {
    param([string]$Task, [string]$TaskId)
    
    $taskFile = "$TasksDir\$TaskId.json"
    $task = @{
        id = $TaskId
        task = $Task
        status = "processing"
        started = (Get-Date).ToString('o')
        result = $null
    }
    $task | ConvertTo-Json | Set-Content $taskFile
    
    # Start background job
    $job = Start-Job -ScriptBlock {
        param($TaskText, $TaskFile, $Model)
        
        # Deep thinking prompt
        $prompt = @"
You are the BACK-END REASONING CORE. Think deeply and thoroughly.
Task: $TaskText

Provide detailed analysis, step-by-step reasoning, and comprehensive results.
"@
        
        $result = ollama run $Model $prompt
        
        # Save result
        $taskData = Get-Content $TaskFile | ConvertFrom-Json
        $taskData.status = "completed"
        $taskData.result = $result
        $taskData.completed = (Get-Date).ToString('o')
        $taskData | ConvertTo-Json | Set-Content $TaskFile
        
        return $result
    } -ArgumentList $Task, $taskFile, "llama3.2"
    
    return @{
        jobId = $job.Id
        taskId = $TaskId
        taskFile = $taskFile
    }
}

function Get-BackendStatus {
    param([string]$TaskId)
    
    $taskFile = "$TasksDir\$TaskId.json"
    if (Test-Path $taskFile) {
        return Get-Content $taskFile | ConvertFrom-Json
    }
    return $null
}

function Get-AllTasks {
    $tasks = Get-ChildItem "$TasksDir\*.json" -ErrorAction SilentlyContinue
    return $tasks | ForEach-Object {
        Get-Content $_.FullName | ConvertFrom-Json
    }
}

#endregion

#region Front-End (Fast Response)

function Invoke-FrontEnd {
    param([string]$UserMessage)
    
    Write-Host "`n[FRONT-END] " -NoNewline -ForegroundColor Green
    
    # Quick analysis - should we spawn back-end?
    $needsDeepThinking = $UserMessage -match '(analyze|research|calculate|plan|design|build|create|complex)'
    
    if ($needsDeepThinking) {
        # Spawn back-end thread
        $taskId = "task_$(Get-Random)"
        $thread = Start-BackendThread -Task $UserMessage -TaskId $taskId
        
        Write-Host "Processing your request..." -ForegroundColor Green
        Write-Host "[BACK-END SPAWNED] Task ID: $taskId" -ForegroundColor Yellow
        
        # Give quick acknowledgment
        $quickResponse = @"
I'm on it! Here's what I'm doing:

FRONT-END (me): Keeping our conversation flowing
BACK-END: Deep analysis running in parallel (Task: $taskId)

I can answer other questions while that processes. What else?
"@
        
        Write-Host $quickResponse -ForegroundColor White
        
        return @{
            response = $quickResponse
            backendTask = $thread
        }
    }
    else {
        # Simple response - no need for back-end
        $prompt = "You are a helpful AI assistant. Respond briefly: $UserMessage"
        $response = ollama run llama3.2 $prompt
        Write-Host $response -ForegroundColor White
        
        return @{
            response = $response
            backendTask = $null
        }
    }
}

#endregion

#region Streaming Thought Display

function Show-ThoughtStream {
    param([string]$TaskId)
    
    Write-Host "`n========== THOUGHT STREAM ==========" -ForegroundColor Cyan
    Write-Host "Back-End Reasoning for Task: $TaskId" -ForegroundColor Gray
    Write-Host "=====================================" -ForegroundColor Cyan
    
    # Monitor task file for updates
    $taskFile = "$TasksDir\$TaskId.json"
    $lastStatus = ""
    
    while ($true) {
        if (Test-Path $taskFile) {
            $task = Get-Content $taskFile | ConvertFrom-Json
            
            if ($task.status -ne $lastStatus) {
                Write-Host "`n[STATUS] $($task.status)" -ForegroundColor Yellow
                $lastStatus = $task.status
            }
            
            if ($task.status -eq "completed") {
                Write-Host "`n[RESULT]" -ForegroundColor Green
                Write-Host $task.result -ForegroundColor White
                break
            }
        }
        
        Start-Sleep -Milliseconds 500
    }
    
    Write-Host "`n====================================`n" -ForegroundColor Cyan
}

#endregion

#region Watchdog (Autonomous Monitor)

function Start-Watchdog {
    param([string]$Goal, [int]$CheckIntervalSeconds = 30)
    
    $watchdog = @{
        goal = $Goal
        started = (Get-Date).ToString('o')
        checks = @()
        status = "active"
    }
    $watchdog | ConvertTo-Json | Set-Content $WatchdogFile
    
    # Start watchdog job
    $job = Start-Job -ScriptBlock {
        param($Goal, $Interval, $WatchdogFile, $TasksDir)
        
        while ($true) {
            $watchdog = Get-Content $WatchdogFile | ConvertFrom-Json
            
            if ($watchdog.status -ne "active") {
                break
            }
            
            # Check tasks
            $tasks = Get-ChildItem "$TasksDir\*.json" -ErrorAction SilentlyContinue
            $completed = ($tasks | Where-Object { 
                $t = Get-Content $_.FullName | ConvertFrom-Json
                $t.status -eq "completed"
            }).Count
            $total = $tasks.Count
            
            # Create check entry
            $check = @{
                timestamp = (Get-Date).ToString('o')
                tasksCompleted = $completed
                tasksTotal = $total
                progress = if ($total -gt 0) { [math]::Round(($completed / $total) * 100, 2) } else { 0 }
            }
            
            # Update watchdog
            $watchdog.checks += $check
            $watchdog | ConvertTo-Json -Depth 10 | Set-Content $WatchdogFile
            
            Start-Sleep -Seconds $Interval
        }
    } -ArgumentList $Goal, $CheckIntervalSeconds, $WatchdogFile, $TasksDir
    
    Write-Host "`n[WATCHDOG STARTED]" -ForegroundColor Magenta
    Write-Host "Goal: $Goal" -ForegroundColor White
    Write-Host "Monitoring every $CheckIntervalSeconds seconds" -ForegroundColor Gray
    Write-Host "Job ID: $($job.Id)`n" -ForegroundColor Gray
    
    return $job
}

function Get-WatchdogStatus {
    if (Test-Path $WatchdogFile) {
        $watchdog = Get-Content $WatchdogFile | ConvertFrom-Json
        
        Write-Host "`n========== WATCHDOG STATUS ==========" -ForegroundColor Magenta
        Write-Host "Goal: $($watchdog.goal)" -ForegroundColor White
        Write-Host "Started: $($watchdog.started)" -ForegroundColor Gray
        Write-Host "Status: $($watchdog.status)" -ForegroundColor Yellow
        
        if ($watchdog.checks.Count -gt 0) {
            $lastCheck = $watchdog.checks[-1]
            Write-Host "`nLatest Check:" -ForegroundColor Cyan
            Write-Host "  Time: $($lastCheck.timestamp)" -ForegroundColor Gray
            Write-Host "  Progress: $($lastCheck.progress)%" -ForegroundColor Green
            Write-Host "  Tasks: $($lastCheck.tasksCompleted)/$($lastCheck.tasksTotal)" -ForegroundColor Gray
        }
        
        Write-Host "====================================`n" -ForegroundColor Magenta
    }
    else {
        Write-Host "No watchdog running" -ForegroundColor Yellow
    }
}

function Stop-Watchdog {
    if (Test-Path $WatchdogFile) {
        $watchdog = Get-Content $WatchdogFile | ConvertFrom-Json
        $watchdog.status = "stopped"
        $watchdog | ConvertTo-Json | Set-Content $WatchdogFile
        
        Write-Host "[WATCHDOG STOPPED]" -ForegroundColor Magenta
    }
}

#endregion

#region Interactive Mode

function Start-ThreadedMode {
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   SubZero - Thread-Split Architecture   ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "`nFEATURES:" -ForegroundColor Yellow
    Write-Host "  • Front-End: Fast responses" -ForegroundColor Green
    Write-Host "  • Back-End: Deep thinking (parallel)" -ForegroundColor Blue
    Write-Host "  • Watchdog: Autonomous monitoring" -ForegroundColor Magenta
    Write-Host "`nCOMMANDS:" -ForegroundColor Yellow
    Write-Host "  tasks     - List all tasks" -ForegroundColor Gray
    Write-Host "  watch     - Start watchdog" -ForegroundColor Gray
    Write-Host "  status    - Watchdog status" -ForegroundColor Gray
    Write-Host "  stream ID - View thought stream" -ForegroundColor Gray
    Write-Host "  exit      - Quit`n" -ForegroundColor Gray
    
    while ($true) {
        Write-Host "You: " -NoNewline -ForegroundColor White
        $input = Read-Host
        
        if ($input -eq 'exit') {
            Stop-Watchdog
            Write-Host "`nShutting down all threads..." -ForegroundColor Cyan
            break
        }
        
        if ($input -eq 'tasks') {
            $allTasks = Get-AllTasks
            if ($allTasks) {
                Write-Host "`n[TASKS]" -ForegroundColor Yellow
                $allTasks | ForEach-Object {
                    $status = if ($_.status -eq "completed") { "✓" } else { "..." }
                    Write-Host "  $status $($_.id): $($_.task.Substring(0, [Math]::Min(50, $_.task.Length)))..." -ForegroundColor Gray
                }
                Write-Host ""
            }
            else {
                Write-Host "No tasks yet" -ForegroundColor Gray
            }
            continue
        }
        
        if ($input -eq 'watch') {
            Write-Host "Enter goal: " -NoNewline -ForegroundColor Yellow
            $goal = Read-Host
            Start-Watchdog -Goal $goal
            continue
        }
        
        if ($input -eq 'status') {
            Get-WatchdogStatus
            continue
        }
        
        if ($input -match '^stream\s+(.+)$') {
            Show-ThoughtStream -TaskId $matches[1]
            continue
        }
        
        if ($input) {
            Invoke-FrontEnd -UserMessage $input
        }
    }
}

#endregion

#region Main Entry

if ($Mode -eq "watchdog") {
    Start-Watchdog -Goal $Message
}
elseif ($Message) {
    Invoke-FrontEnd -UserMessage $Message
}
else {
    Start-ThreadedMode
}

#endregion
