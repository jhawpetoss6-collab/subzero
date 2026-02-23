# SubZero Agent Mesh - Swarm with Inter-Agent Communication
# Agents can talk to each other and share task status

param(
    [string]$Message,
    [string]$Agent = "main",
    [switch]$ListAgents,
    [switch]$ShowMesh
)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$AgentsDir = "$SubZeroHome\agents"
$MessagesDir = "$SubZeroHome\messages"
$TaskRegistryFile = "$SubZeroHome\task-registry.json"
$KnowledgeBaseFile = "$SubZeroHome\knowledge-base.json"

# Initialize
@($SubZeroHome, $AgentsDir, $MessagesDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ | Out-Null }
}

#region Agent Registry

function Register-Agent {
    param([string]$Name, [string]$Role, [string]$Capabilities)
    
    $agentFile = "$AgentsDir\$Name.json"
    $agent = @{
        name = $Name
        role = $Role
        capabilities = $Capabilities
        status = "active"
        created = (Get-Date).ToString('o')
        lastSeen = (Get-Date).ToString('o')
        tasksCompleted = @()
        currentTask = $null
    }
    
    $agent | ConvertTo-Json -Depth 10 | Set-Content $agentFile
    
    # Broadcast to other agents
    Send-AgentMessage -From $Name -To "ALL" -Type "join" -Content "New agent joined: $Name ($Role)"
    
    return $agent
}

function Get-AllAgents {
    $agents = Get-ChildItem "$AgentsDir\*.json" -ErrorAction SilentlyContinue
    return $agents | ForEach-Object {
        Get-Content $_.FullName | ConvertFrom-Json
    }
}

function Update-AgentStatus {
    param([string]$Name, [string]$Status, [string]$CurrentTask = $null)
    
    $agentFile = "$AgentsDir\$Name.json"
    if (Test-Path $agentFile) {
        $agent = Get-Content $agentFile | ConvertFrom-Json
        $agent.status = $Status
        $agent.lastSeen = (Get-Date).ToString('o')
        if ($CurrentTask) {
            $agent.currentTask = $CurrentTask
        }
        $agent | ConvertTo-Json -Depth 10 | Set-Content $agentFile
    }
}

#endregion

#region Task Registry (Shared Task Tracking)

function Initialize-TaskRegistry {
    if (!(Test-Path $TaskRegistryFile)) {
        $registry = @{
            tasks = @()
            lastUpdate = (Get-Date).ToString('o')
        }
        $registry | ConvertTo-Json | Set-Content $TaskRegistryFile
    }
}

function Register-Task {
    param(
        [string]$TaskId,
        [string]$Description,
        [string]$AssignedTo,
        [string]$Status = "pending"
    )
    
    Initialize-TaskRegistry
    $registry = Get-Content $TaskRegistryFile | ConvertFrom-Json
    
    # Check if task already exists or is similar
    $existingTask = $registry.tasks | Where-Object { 
        $_.description -eq $Description -or $_.id -eq $TaskId 
    }
    
    if ($existingTask) {
        Write-Host "[TASK REGISTRY] Similar task already exists: $($existingTask.id)" -ForegroundColor Yellow
        Write-Host "  Assigned to: $($existingTask.assignedTo)" -ForegroundColor Gray
        Write-Host "  Status: $($existingTask.status)" -ForegroundColor Gray
        return $existingTask
    }
    
    $task = @{
        id = $TaskId
        description = $Description
        assignedTo = $AssignedTo
        status = $Status
        created = (Get-Date).ToString('o')
        updated = (Get-Date).ToString('o')
        result = $null
    }
    
    $registry.tasks += $task
    $registry.lastUpdate = (Get-Date).ToString('o')
    $registry | ConvertTo-Json -Depth 10 | Set-Content $TaskRegistryFile
    
    # Notify all agents
    Send-AgentMessage -From $AssignedTo -To "ALL" -Type "task_registered" -Content "New task: $Description"
    
    return $task
}

function Update-TaskStatus {
    param(
        [string]$TaskId,
        [string]$Status,
        [string]$Result = $null
    )
    
    $registry = Get-Content $TaskRegistryFile | ConvertFrom-Json
    $task = $registry.tasks | Where-Object { $_.id -eq $TaskId }
    
    if ($task) {
        $task.status = $Status
        $task.updated = (Get-Date).ToString('o')
        if ($Result) {
            $task.result = $Result
        }
        
        $registry | ConvertTo-Json -Depth 10 | Set-Content $TaskRegistryFile
        
        # Notify all agents
        Send-AgentMessage -From $task.assignedTo -To "ALL" -Type "task_update" -Content "Task $TaskId status: $Status"
    }
}

function Get-TaskRegistry {
    Initialize-TaskRegistry
    return Get-Content $TaskRegistryFile | ConvertFrom-Json
}

#endregion

#region Message Bus (Agent-to-Agent Communication)

function Send-AgentMessage {
    param(
        [string]$From,
        [string]$To,  # Agent name or "ALL" for broadcast
        [string]$Type,  # join, task_registered, task_update, query, response
        [string]$Content
    )
    
    $messageId = "msg_$(Get-Random)"
    $messageFile = "$MessagesDir\$messageId.json"
    
    $message = @{
        id = $messageId
        from = $From
        to = $To
        type = $Type
        content = $Content
        timestamp = (Get-Date).ToString('o')
        read = $false
    }
    
    $message | ConvertTo-Json | Set-Content $messageFile
}

function Get-AgentMessages {
    param([string]$AgentName, [switch]$Unread)
    
    $messages = Get-ChildItem "$MessagesDir\*.json" -ErrorAction SilentlyContinue | ForEach-Object {
        Get-Content $_.FullName | ConvertFrom-Json
    }
    
    # Filter for this agent or broadcasts
    $filtered = $messages | Where-Object { 
        $_.to -eq $AgentName -or $_.to -eq "ALL"
    }
    
    if ($Unread) {
        $filtered = $filtered | Where-Object { -not $_.read }
    }
    
    return $filtered | Sort-Object timestamp
}

function Mark-MessageRead {
    param([string]$MessageId)
    
    $messageFile = "$MessagesDir\$MessageId.json"
    if (Test-Path $messageFile) {
        $message = Get-Content $messageFile | ConvertFrom-Json
        $message.read = $true
        $message | ConvertTo-Json | Set-Content $messageFile
    }
}

#endregion

#region Knowledge Base (Shared Learning)

function Initialize-KnowledgeBase {
    if (!(Test-Path $KnowledgeBaseFile)) {
        $kb = @{
            facts = @()
            lastUpdate = (Get-Date).ToString('o')
        }
        $kb | ConvertTo-Json | Set-Content $KnowledgeBaseFile
    }
}

function Add-Knowledge {
    param(
        [string]$Agent,
        [string]$Topic,
        [string]$Information
    )
    
    Initialize-KnowledgeBase
    $kb = Get-Content $KnowledgeBaseFile | ConvertFrom-Json
    
    $fact = @{
        topic = $Topic
        information = $Information
        contributedBy = $Agent
        timestamp = (Get-Date).ToString('o')
    }
    
    $kb.facts += $fact
    $kb.lastUpdate = (Get-Date).ToString('o')
    $kb | ConvertTo-Json -Depth 10 | Set-Content $KnowledgeBaseFile
    
    # Notify agents
    Send-AgentMessage -From $Agent -To "ALL" -Type "knowledge_added" -Content "New knowledge: $Topic"
}

function Query-KnowledgeBase {
    param([string]$Topic)
    
    Initialize-KnowledgeBase
    $kb = Get-Content $KnowledgeBaseFile | ConvertFrom-Json
    
    return $kb.facts | Where-Object { $_.topic -like "*$Topic*" }
}

#endregion

#region Agent Communication Functions

function Invoke-AgentChat {
    param(
        [string]$AgentName,
        [string]$UserMessage
    )
    
    # Update agent status
    Update-AgentStatus -Name $AgentName -Status "active" -CurrentTask $UserMessage
    
    # Check messages from other agents
    $unreadMessages = Get-AgentMessages -AgentName $AgentName -Unread
    
    # Check task registry for similar work
    $registry = Get-TaskRegistry
    $similarTasks = $registry.tasks | Where-Object { 
        $_.description -like "*$($UserMessage.Split(' ')[0])*" -and 
        $_.status -eq "completed" 
    }
    
    # Build context with agent awareness
    $contextPrompt = @"
You are agent: $AgentName

RECENT MESSAGES FROM OTHER AGENTS:
$(if ($unreadMessages) {
    $unreadMessages | ForEach-Object { "- [$($_.from)]: $($_.content)" }
} else { "No new messages" })

COMPLETED TASKS BY OTHER AGENTS:
$(if ($similarTasks) {
    $similarTasks | ForEach-Object { "- $($_.description) by $($_.assignedTo)" }
} else { "No similar completed tasks" })

USER REQUEST: $UserMessage

If other agents have done similar work, acknowledge it and build upon it.
If this is duplicate work, say so and reference the other agent's work.
"@
    
    Write-Host "`n[$AgentName] " -NoNewline -ForegroundColor Cyan
    
    # Get AI response
    $response = ollama run llama3.2 $contextPrompt
    Write-Host $response -ForegroundColor White
    
    # Register task
    $taskId = "task_$(Get-Random)"
    Register-Task -TaskId $taskId -Description $UserMessage -AssignedTo $AgentName
    
    # Mark messages as read
    $unreadMessages | ForEach-Object { Mark-MessageRead -MessageId $_.id }
    
    # Update task as completed
    Update-TaskStatus -TaskId $taskId -Status "completed" -Result $response
    
    # Add to knowledge base
    Add-Knowledge -Agent $AgentName -Topic $UserMessage -Information $response
    
    return $response
}

#endregion

#region Visualization

function Show-AgentMesh {
    Write-Host "`n========== AGENT MESH ==========" -ForegroundColor Cyan
    
    $agents = Get-AllAgents
    if (!$agents) {
        Write-Host "No agents in mesh yet" -ForegroundColor Gray
        return
    }
    
    Write-Host "`nACTIVE AGENTS:" -ForegroundColor Yellow
    $agents | ForEach-Object {
        $status = if ($_.status -eq "active") { "[ONLINE]" } else { "[OFFLINE]" }
        Write-Host "  $status $($_.name)" -ForegroundColor Green
        Write-Host "    Role: $($_.role)" -ForegroundColor Gray
        Write-Host "    Tasks Done: $($_.tasksCompleted.Count)" -ForegroundColor Gray
        if ($_.currentTask) {
            Write-Host "    Current: $($_.currentTask)" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`nTASK REGISTRY:" -ForegroundColor Yellow
    $registry = Get-TaskRegistry
    $pending = ($registry.tasks | Where-Object { $_.status -eq "pending" }).Count
    $completed = ($registry.tasks | Where-Object { $_.status -eq "completed" }).Count
    Write-Host "  Pending: $pending" -ForegroundColor Yellow
    Write-Host "  Completed: $completed" -ForegroundColor Green
    
    Write-Host "`nKNOWLEDGE BASE:" -ForegroundColor Yellow
    $kb = Get-Content $KnowledgeBaseFile -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($kb) {
        Write-Host "  Facts: $($kb.facts.Count)" -ForegroundColor Gray
    }
    
    Write-Host "`nMESSAGES:" -ForegroundColor Yellow
    $allMessages = Get-ChildItem "$MessagesDir\*.json" -ErrorAction SilentlyContinue
    $unread = ($allMessages | ForEach-Object { Get-Content $_.FullName | ConvertFrom-Json } | Where-Object { -not $_.read }).Count
    Write-Host "  Total: $($allMessages.Count)" -ForegroundColor Gray
    Write-Host "  Unread: $unread" -ForegroundColor Yellow
    
    Write-Host "`n================================`n" -ForegroundColor Cyan
}

#endregion

#region Interactive Mode

function Start-MeshMode {
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║     SubZero Agent Mesh (Swarm)          ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "`nAgents communicate and share task status!" -ForegroundColor Green
    Write-Host "`nCOMMANDS:" -ForegroundColor Yellow
    Write-Host "  spawn <name> <role> - Create new agent" -ForegroundColor Gray
    Write-Host "  agents              - List all agents" -ForegroundColor Gray
    Write-Host "  mesh                - Show mesh status" -ForegroundColor Gray
    Write-Host "  tasks               - View task registry" -ForegroundColor Gray
    Write-Host "  messages            - View messages" -ForegroundColor Gray
    Write-Host "  switch <agent>      - Switch to agent" -ForegroundColor Gray
    Write-Host "  exit                - Quit`n" -ForegroundColor Gray
    
    $currentAgent = "main"
    
    # Register main agent if not exists
    if (!(Test-Path "$AgentsDir\main.json")) {
        Register-Agent -Name "main" -Role "Coordinator" -Capabilities "General tasks"
    }
    
    while ($true) {
        Write-Host "[$currentAgent] You: " -NoNewline -ForegroundColor Green
        $input = Read-Host
        
        if ($input -eq 'exit') {
            Write-Host "Shutting down mesh..." -ForegroundColor Cyan
            break
        }
        
        if ($input -match '^spawn\s+(\w+)\s+(.+)$') {
            $agentName = $matches[1]
            $agentRole = $matches[2]
            Register-Agent -Name $agentName -Role $agentRole -Capabilities "To be defined"
            Write-Host "Agent spawned: $agentName" -ForegroundColor Green
            continue
        }
        
        if ($input -eq 'agents') {
            $agents = Get-AllAgents
            Write-Host "`nAGENTS:" -ForegroundColor Yellow
            $agents | ForEach-Object {
                Write-Host "  - $($_.name): $($_.role)" -ForegroundColor Cyan
            }
            continue
        }
        
        if ($input -eq 'mesh') {
            Show-AgentMesh
            continue
        }
        
        if ($input -eq 'tasks') {
            $registry = Get-TaskRegistry
            Write-Host "`nTASKS:" -ForegroundColor Yellow
            $registry.tasks | ForEach-Object {
                $statusColor = if ($_.status -eq "completed") { "Green" } else { "Yellow" }
                Write-Host "  [$($_.status)] $($_.description)" -ForegroundColor $statusColor
                Write-Host "    Assigned: $($_.assignedTo)" -ForegroundColor Gray
            }
            continue
        }
        
        if ($input -eq 'messages') {
            $messages = Get-AgentMessages -AgentName $currentAgent
            Write-Host "`nMESSAGES for $currentAgent:" -ForegroundColor Yellow
            $messages | ForEach-Object {
                $readStatus = if ($_.read) { "[READ]" } else { "[NEW]" }
                Write-Host "  $readStatus From $($_.from): $($_.content)" -ForegroundColor Cyan
            }
            continue
        }
        
        if ($input -match '^switch\s+(\w+)$') {
            $newAgent = $matches[1]
            if (Test-Path "$AgentsDir\$newAgent.json") {
                $currentAgent = $newAgent
                Write-Host "Switched to agent: $currentAgent" -ForegroundColor Green
            } else {
                Write-Host "Agent not found: $newAgent" -ForegroundColor Red
            }
            continue
        }
        
        if ($input) {
            Invoke-AgentChat -AgentName $currentAgent -UserMessage $input
        }
    }
}

#endregion

#region Main Entry

if ($ListAgents) {
    Get-AllAgents | ForEach-Object {
        Write-Host "$($_.name): $($_.role)" -ForegroundColor Cyan
    }
}
elseif ($ShowMesh) {
    Show-AgentMesh
}
elseif ($Message) {
    Invoke-AgentChat -AgentName $Agent -UserMessage $Message
}
else {
    Start-MeshMode
}

#endregion
