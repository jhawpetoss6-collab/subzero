# SubZero Swarm - Coordinated Multi-Agent System
# Multiple agents communicate to avoid duplicate work
# Shared task queue + status tracking

param([switch]$Debug)

$SwarmHome = "$env:USERPROFILE\.subzero\swarm"
$TaskQueue = "$SwarmHome\task_queue.json"
$AgentRegistry = "$SwarmHome\agent_registry.json"
$MessageBus = "$SwarmHome\message_bus.json"
$CompletedTasks = "$SwarmHome\completed_tasks.json"

# Initialize
if (!(Test-Path $SwarmHome)) { New-Item -ItemType Directory -Path $SwarmHome -Force | Out-Null }

# SWARM COORDINATION SYSTEM
$swarm = @{
    agents = @()
    task_queue = @()
    completed = @()
    in_progress = @{}
    message_bus = @()
}

# Load persistent state
if (Test-Path $TaskQueue) {
    $swarm.task_queue = Get-Content $TaskQueue | ConvertFrom-Json
}
if (Test-Path $CompletedTasks) {
    $swarm.completed = Get-Content $CompletedTasks | ConvertFrom-Json
}
if (Test-Path $MessageBus) {
    $swarm.message_bus = Get-Content $MessageBus | ConvertFrom-Json
}

# Agent definitions with specialties
$agentDefinitions = @{
    Coder = @{
        id = "agent_coder"
        specialty = "code_creation"
        capabilities = @("create_file", "edit_file", "write_code")
        status = "idle"
        current_task = $null
    }
    
    Tester = @{
        id = "agent_tester"
        specialty = "testing"
        capabilities = @("run_tests", "validate_code", "check_quality")
        status = "idle"
        current_task = $null
    }
    
    Researcher = @{
        id = "agent_researcher"
        specialty = "research"
        capabilities = @("gather_info", "analyze_docs", "summarize")
        status = "idle"
        current_task = $null
    }
    
    Debugger = @{
        id = "agent_debugger"
        specialty = "debugging"
        capabilities = @("find_bugs", "fix_errors", "optimize")
        status = "idle"
        current_task = $null
    }
    
    Documenter = @{
        id = "agent_documenter"
        specialty = "documentation"
        capabilities = @("write_docs", "create_readme", "comment_code")
        status = "idle"
        current_task = $null
    }
}

# Initialize agents
foreach ($agent in $agentDefinitions.Keys) {
    $swarm.agents += $agentDefinitions[$agent]
}

# SWARM COMMUNICATION PROTOCOL

function Broadcast-Message {
    param($from_agent, $message_type, $content)
    
    $message = @{
        from = $from_agent
        type = $message_type
        content = $content
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        id = Get-Random
    }
    
    $script:swarm.message_bus += $message
    Save-MessageBus
    
    Write-Host "[BROADCAST] " -NoNewline -ForegroundColor Magenta
    Write-Host "$from_agent → All: $message_type" -ForegroundColor Gray
}

function Send-DirectMessage {
    param($from_agent, $to_agent, $message_type, $content)
    
    $message = @{
        from = $from_agent
        to = $to_agent
        type = $message_type
        content = $content
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        id = Get-Random
    }
    
    $script:swarm.message_bus += $message
    Save-MessageBus
    
    Write-Host "[MESSAGE] " -NoNewline -ForegroundColor Cyan
    Write-Host "$from_agent → $to_agent: $message_type" -ForegroundColor Gray
}

function Check-TaskStatus {
    param($task_id)
    
    # Check if task is completed
    if ($swarm.completed | Where-Object { $_.id -eq $task_id }) {
        return "completed"
    }
    
    # Check if task is in progress
    if ($swarm.in_progress.ContainsKey($task_id)) {
        return "in_progress"
    }
    
    # Check if task is in queue
    if ($swarm.task_queue | Where-Object { $_.id -eq $task_id }) {
        return "queued"
    }
    
    return "unknown"
}

function Claim-Task {
    param($agent_id, $task_id)
    
    # Check if already claimed or completed
    $status = Check-TaskStatus $task_id
    
    if ($status -eq "completed") {
        Broadcast-Message $agent_id "task_skip" "Task $task_id already completed"
        return $false
    }
    
    if ($status -eq "in_progress") {
        $currentOwner = $swarm.in_progress[$task_id]
        Broadcast-Message $agent_id "task_conflict" "Task $task_id already claimed by $currentOwner"
        return $false
    }
    
    # Claim the task
    $script:swarm.in_progress[$task_id] = $agent_id
    Broadcast-Message $agent_id "task_claim" "Claimed task $task_id"
    
    # Update agent status
    $agent = $swarm.agents | Where-Object { $_.id -eq $agent_id }
    $agent.status = "working"
    $agent.current_task = $task_id
    
    return $true
}

function Complete-Task {
    param($agent_id, $task_id, $result)
    
    # Remove from in_progress
    $script:swarm.in_progress.Remove($task_id)
    
    # Add to completed
    $task = $swarm.task_queue | Where-Object { $_.id -eq $task_id }
    if ($task) {
        $task.completed_by = $agent_id
        $task.completed_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $task.result = $result
        $script:swarm.completed += $task
    }
    
    # Remove from queue
    $script:swarm.task_queue = $swarm.task_queue | Where-Object { $_.id -ne $task_id }
    
    # Update agent status
    $agent = $swarm.agents | Where-Object { $_.id -eq $agent_id }
    $agent.status = "idle"
    $agent.current_task = $null
    
    Broadcast-Message $agent_id "task_complete" "Completed task $task_id"
    
    Save-State
}

function Add-TaskToQueue {
    param($description, $task_type, $priority = "medium", $deadline = $null, $assignedTo = $null)
    
    $task = @{
        id = "task_$(Get-Random)"
        description = $description
        type = $task_type
        priority = $priority
        created_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        status = "queued"
        deadline = $deadline
        assigned_to = $assignedTo
        tags = @()
        dependencies = @()
        estimated_time = $null
    }
    
    $script:swarm.task_queue += $task
    Save-State
    
    Write-Host "[TASK ADDED] " -NoNewline -ForegroundColor Yellow
    Write-Host "$($task.id): $description" -ForegroundColor White
    
    # Notify all agents
    Broadcast-Message "system" "new_task" $task.id
    
    return $task.id
}

function Find-BestAgent {
    param($task_type)
    
    # Find idle agents with matching specialty
    $matchingAgents = $swarm.agents | Where-Object { 
        $_.status -eq "idle" -and $_.specialty -eq $task_type
    }
    
    if ($matchingAgents) {
        return $matchingAgents[0]
    }
    
    # Fallback: any idle agent
    $idleAgents = $swarm.agents | Where-Object { $_.status -eq "idle" }
    if ($idleAgents) {
        return $idleAgents[0]
    }
    
    return $null
}

function Process-TaskQueue {
    # Process pending tasks
    foreach ($task in $swarm.task_queue) {
        # Skip if already in progress
        if (Check-TaskStatus $task.id -eq "in_progress") {
            continue
        }
        
        # Find best agent
        $agent = Find-BestAgent $task.type
        
        if ($agent) {
            Write-Host ""
            Write-Host "[ASSIGNMENT] " -NoNewline -ForegroundColor Green
            Write-Host "Assigning task $($task.id) to $($agent.id)" -ForegroundColor White
            
            if (Claim-Task $agent.id $task.id) {
                # Simulate work
                Start-Sleep -Milliseconds 500
                
                # Complete task
                Complete-Task $agent.id $task.id "Success"
            }
        } else {
            Write-Host "[WAITING] " -NoNewline -ForegroundColor Yellow
            Write-Host "No idle agents for task $($task.id)" -ForegroundColor Gray
        }
    }
}

function Save-State {
    $swarm.task_queue | ConvertTo-Json -Depth 10 | Set-Content $TaskQueue
    $swarm.completed | ConvertTo-Json -Depth 10 | Set-Content $CompletedTasks
}

function Save-MessageBus {
    # Keep only last 50 messages
    if ($swarm.message_bus.Count -gt 50) {
        $script:swarm.message_bus = $swarm.message_bus | Select-Object -Last 50
    }
    $swarm.message_bus | ConvertTo-Json -Depth 10 | Set-Content $MessageBus
}

# TASK MANAGEMENT FUNCTIONS

function Set-TaskPriority {
    param($task_id, $priority)
    
    $task = $swarm.task_queue | Where-Object { $_.id -eq $task_id }
    if ($task) {
        $task.priority = $priority
        Save-State
        Write-Host "✓ Task $task_id priority set to $priority" -ForegroundColor Green
        Broadcast-Message "system" "priority_changed" "Task $task_id now $priority priority"
    } else {
        Write-Host "✗ Task $task_id not found" -ForegroundColor Red
    }
}

function Set-TaskDeadline {
    param($task_id, $deadline)
    
    $task = $swarm.task_queue | Where-Object { $_.id -eq $task_id }
    if ($task) {
        try {
            $deadlineDate = [DateTime]::Parse($deadline)
            $task.deadline = $deadlineDate.ToString("yyyy-MM-dd HH:mm")
            Save-State
            Write-Host "✓ Task $task_id deadline set to $($task.deadline)" -ForegroundColor Green
            Broadcast-Message "system" "deadline_set" "Task $task_id deadline: $($task.deadline)"
        } catch {
            Write-Host "✗ Invalid date format. Use: YYYY-MM-DD or 'tomorrow', 'next week'" -ForegroundColor Red
        }
    } else {
        Write-Host "✗ Task $task_id not found" -ForegroundColor Red
    }
}

function Assign-TaskToAgent {
    param($task_id, $agent_id)
    
    $task = $swarm.task_queue | Where-Object { $_.id -eq $task_id }
    $agent = $swarm.agents | Where-Object { $_.id -eq $agent_id }
    
    if (!$task) {
        Write-Host "✗ Task $task_id not found" -ForegroundColor Red
        return
    }
    
    if (!$agent) {
        Write-Host "✗ Agent $agent_id not found" -ForegroundColor Red
        return
    }
    
    $task.assigned_to = $agent_id
    Save-State
    Write-Host "✓ Task $task_id assigned to $agent_id" -ForegroundColor Green
    Send-DirectMessage "system" $agent_id "task_assigned" $task_id
}

function Cancel-Task {
    param($task_id)
    
    $task = $swarm.task_queue | Where-Object { $_.id -eq $task_id }
    if ($task) {
        $script:swarm.task_queue = $swarm.task_queue | Where-Object { $_.id -ne $task_id }
        
        # Remove from in_progress if claimed
        if ($swarm.in_progress.ContainsKey($task_id)) {
            $agent_id = $swarm.in_progress[$task_id]
            $script:swarm.in_progress.Remove($task_id)
            
            # Free up agent
            $agent = $swarm.agents | Where-Object { $_.id -eq $agent_id }
            $agent.status = "idle"
            $agent.current_task = $null
        }
        
        Save-State
        Write-Host "✓ Task $task_id cancelled" -ForegroundColor Green
        Broadcast-Message "system" "task_cancelled" $task_id
    } else {
        Write-Host "✗ Task $task_id not found" -ForegroundColor Red
    }
}

function Get-OverdueTasks {
    $now = Get-Date
    $overdue = @()
    
    foreach ($task in $swarm.task_queue) {
        if ($task.deadline) {
            try {
                $deadlineDate = [DateTime]::Parse($task.deadline)
                if ($deadlineDate -lt $now) {
                    $overdue += $task
                }
            } catch { }
        }
    }
    
    return $overdue
}

function Show-TaskDetails {
    Write-Host ""
    Write-Host "═══ ALL TASKS ═══" -ForegroundColor Cyan
    Write-Host ""
    
    if ($swarm.task_queue.Count -eq 0) {
        Write-Host "  No pending tasks" -ForegroundColor Gray
        Write-Host ""
        return
    }
    
    # Sort by priority
    $priorityOrder = @{ "high" = 1; "medium" = 2; "low" = 3 }
    $sorted = $swarm.task_queue | Sort-Object { $priorityOrder[$_.priority] }
    
    foreach ($task in $sorted) {
        # Priority badge
        $priorityColor = switch ($task.priority) {
            "high" { "Red" }
            "medium" { "Yellow" }
            "low" { "Gray" }
        }
        
        Write-Host "  " -NoNewline
        Write-Host "[$($task.priority.ToUpper())]" -NoNewline -ForegroundColor $priorityColor
        Write-Host " $($task.id)" -ForegroundColor White
        Write-Host "      $($task.description)" -ForegroundColor Gray
        
        # Status
        if ($swarm.in_progress.ContainsKey($task.id)) {
            $agent_id = $swarm.in_progress[$task.id]
            Write-Host "      Status: " -NoNewline -ForegroundColor DarkGray
            Write-Host "In Progress by $agent_id" -ForegroundColor Yellow
        } elseif ($task.assigned_to) {
            Write-Host "      Assigned: " -NoNewline -ForegroundColor DarkGray
            Write-Host $task.assigned_to -ForegroundColor Cyan
        } else {
            Write-Host "      Status: " -NoNewline -ForegroundColor DarkGray
            Write-Host "Queued" -ForegroundColor Gray
        }
        
        # Deadline
        if ($task.deadline) {
            $deadlineDate = [DateTime]::Parse($task.deadline)
            $now = Get-Date
            $timeLeft = $deadlineDate - $now
            
            Write-Host "      Deadline: " -NoNewline -ForegroundColor DarkGray
            if ($timeLeft.TotalHours -lt 0) {
                Write-Host "$($task.deadline) (OVERDUE!)" -ForegroundColor Red
            } elseif ($timeLeft.TotalHours -lt 24) {
                Write-Host "$($task.deadline) (Due soon!)" -ForegroundColor Yellow
            } else {
                Write-Host $task.deadline -ForegroundColor White
            }
        }
        
        Write-Host "      Created: " -NoNewline -ForegroundColor DarkGray
        Write-Host $task.created_at -ForegroundColor DarkGray
        Write-Host ""
    }
}

# WATCHDOG with swarm coordination
function Start-Watchdog {
    Write-Host ""
    Write-Host "═══ WATCHDOG STARTED ═══" -ForegroundColor Yellow
    Write-Host "Monitoring task queue and coordinating agents..." -ForegroundColor Gray
    Write-Host ""
    
    while ($true) {
        # Process queue
        Process-TaskQueue
        
        # Check for conflicts
        foreach ($taskId in $swarm.in_progress.Keys) {
            $task = $swarm.task_queue | Where-Object { $_.id -eq $taskId }
            if (!$task) {
                # Task completed or removed
                $script:swarm.in_progress.Remove($taskId)
            }
        }
        
        # Brief pause
        Start-Sleep -Seconds 2
        
        # Check if all tasks done
        if ($swarm.task_queue.Count -eq 0 -and $swarm.in_progress.Count -eq 0) {
            break
        }
    }
    
    Write-Host ""
    Write-Host "═══ ALL TASKS COMPLETE ═══" -ForegroundColor Green
    Write-Host ""
}

# Main Interface
Clear-Host
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "    SubZero Swarm - Coordinated Multi-Agent System" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "SWARM COORDINATION:" -ForegroundColor Yellow
Write-Host "  ✓ Shared task queue" -ForegroundColor Green
Write-Host "  ✓ Agent-to-agent communication" -ForegroundColor Green
Write-Host "  ✓ Automatic task claiming" -ForegroundColor Green
Write-Host "  ✓ Duplicate work prevention" -ForegroundColor Green
Write-Host "  ✓ Autonomous watchdog" -ForegroundColor Green
Write-Host ""
Write-Host "ACTIVE AGENTS:" -ForegroundColor Yellow
foreach ($agent in $swarm.agents) {
    Write-Host "  • $($agent.id)" -NoNewline -ForegroundColor White
    Write-Host " ($($agent.specialty))" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Commands:" -ForegroundColor Gray
Write-Host "  add <description>      - Add task to queue" -ForegroundColor Gray
Write-Host "  task <id> priority <high/medium/low> - Change priority" -ForegroundColor Gray
Write-Host "  task <id> deadline <date> - Set deadline" -ForegroundColor Gray
Write-Host "  task <id> assign <agent> - Manually assign task" -ForegroundColor Gray
Write-Host "  task <id> cancel       - Cancel/remove task" -ForegroundColor Gray
Write-Host "  tasks                  - List all tasks with details" -ForegroundColor Gray
Write-Host "  status                 - View swarm status" -ForegroundColor Gray
Write-Host "  agents                 - View agent status" -ForegroundColor Gray
Write-Host "  messages               - View message bus" -ForegroundColor Gray
Write-Host "  completed              - View completed tasks" -ForegroundColor Gray
Write-Host "  overdue                - Show overdue tasks" -ForegroundColor Gray
Write-Host "  start watchdog         - Start autonomous processing" -ForegroundColor Gray
Write-Host "  clear                  - Clear completed tasks" -ForegroundColor Gray
Write-Host "  exit                   - Exit" -ForegroundColor Gray
Write-Host ""

# Demo tasks
Write-Host "Loading demo tasks..." -ForegroundColor Cyan
Add-TaskToQueue "Create login page" "code_creation" "high"
Add-TaskToQueue "Write unit tests" "testing" "high"
Add-TaskToQueue "Research best practices" "research" "medium"
Add-TaskToQueue "Fix authentication bug" "debugging" "high"
Add-TaskToQueue "Write API documentation" "documentation" "low"
Write-Host ""

while ($true) {
    Write-Host "Swarm> " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    if ($userInput -eq "exit") {
        Save-State
        Write-Host "`nGoodbye! Completed $($swarm.completed.Count) tasks." -ForegroundColor Yellow
        break
    }
    
    if ($userInput -eq "status") {
        Write-Host ""
        Write-Host "═══ SWARM STATUS ═══" -ForegroundColor Cyan
        Write-Host "Queued:      $($swarm.task_queue.Count) tasks" -ForegroundColor White
        Write-Host "In Progress: $($swarm.in_progress.Count) tasks" -ForegroundColor Yellow
        Write-Host "Completed:   $($swarm.completed.Count) tasks" -ForegroundColor Green
        Write-Host ""
        
        if ($swarm.in_progress.Count -gt 0) {
            Write-Host "Currently Working:" -ForegroundColor Yellow
            foreach ($taskId in $swarm.in_progress.Keys) {
                $agentId = $swarm.in_progress[$taskId]
                Write-Host "  • $taskId → $agentId" -ForegroundColor Gray
            }
            Write-Host ""
        }
        continue
    }
    
    if ($userInput -eq "agents") {
        Write-Host ""
        Write-Host "═══ AGENT STATUS ═══" -ForegroundColor Cyan
        foreach ($agent in $swarm.agents) {
            $statusColor = if ($agent.status -eq "idle") { "Green" } else { "Yellow" }
            Write-Host "  $($agent.id)" -NoNewline -ForegroundColor White
            Write-Host " [$($agent.status)]" -NoNewline -ForegroundColor $statusColor
            Write-Host " - $($agent.specialty)" -ForegroundColor Gray
            if ($agent.current_task) {
                Write-Host "    Working on: $($agent.current_task)" -ForegroundColor DarkGray
            }
        }
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "messages") {
        Write-Host ""
        Write-Host "═══ MESSAGE BUS (Last 10) ═══" -ForegroundColor Cyan
        $swarm.message_bus | Select-Object -Last 10 | ForEach-Object {
            Write-Host "  [$($_.timestamp)] " -NoNewline -ForegroundColor DarkGray
            Write-Host "$($_.from) → " -NoNewline -ForegroundColor White
            if ($_.to) {
                Write-Host "$($_.to): " -NoNewline -ForegroundColor White
            } else {
                Write-Host "ALL: " -NoNewline -ForegroundColor White
            }
            Write-Host "$($_.type)" -ForegroundColor Cyan
        }
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "completed") {
        Write-Host ""
        Write-Host "═══ COMPLETED TASKS ═══" -ForegroundColor Green
        if ($swarm.completed.Count -gt 0) {
            foreach ($task in $swarm.completed) {
                Write-Host "  ✓ $($task.id)" -NoNewline -ForegroundColor Green
                Write-Host " - $($task.description)" -ForegroundColor White
                Write-Host "    By: $($task.completed_by) at $($task.completed_at)" -ForegroundColor Gray
            }
        } else {
            Write-Host "  No completed tasks yet" -ForegroundColor Gray
        }
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "clear") {
        $script:swarm.completed = @()
        Save-State
        Write-Host "Completed tasks cleared" -ForegroundColor Green
        Write-Host ""
        continue
    }
    
    if ($userInput -like "add *") {
        $description = $userInput -replace "add ", ""
        Add-TaskToQueue $description "code_creation" "medium"
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "tasks") {
        Show-TaskDetails
        continue
    }
    
    if ($userInput -eq "overdue") {
        $overdue = Get-OverdueTasks
        Write-Host ""
        Write-Host "═══ OVERDUE TASKS ═══" -ForegroundColor Red
        if ($overdue.Count -gt 0) {
            foreach ($task in $overdue) {
                Write-Host "  ⚠ $($task.id)" -NoNewline -ForegroundColor Red
                Write-Host " - $($task.description)" -ForegroundColor White
                Write-Host "    Deadline was: $($task.deadline)" -ForegroundColor Gray
            }
        } else {
            Write-Host "  No overdue tasks" -ForegroundColor Green
        }
        Write-Host ""
        continue
    }
    
    if ($userInput -like "task * priority *") {
        $parts = $userInput -split ' '
        $taskId = $parts[1]
        $priority = $parts[3]
        Set-TaskPriority $taskId $priority
        Write-Host ""
        continue
    }
    
    if ($userInput -like "task * deadline *") {
        $parts = $userInput -split ' '
        $taskId = $parts[1]
        $deadline = $parts[3..($parts.Length-1)] -join ' '
        Set-TaskDeadline $taskId $deadline
        Write-Host ""
        continue
    }
    
    if ($userInput -like "task * assign *") {
        $parts = $userInput -split ' '
        $taskId = $parts[1]
        $agentId = $parts[3]
        Assign-TaskToAgent $taskId $agentId
        Write-Host ""
        continue
    }
    
    if ($userInput -like "task * cancel") {
        $parts = $userInput -split ' '
        $taskId = $parts[1]
        Cancel-Task $taskId
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "start watchdog") {
        Start-Watchdog
        continue
    }
    
    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    
    Write-Host "Unknown command. Type 'status', 'agents', 'messages', or 'start watchdog'" -ForegroundColor Yellow
    Write-Host ""
}
