# SubZero Warp - Recursive Learning Edition
# AI that learns from every interaction and gets smarter over time

param([switch]$Debug)

$AgentHome = "$env:USERPROFILE\.subzero\warp"
$ProjectsDir = "$AgentHome\projects"
$PlansDir = "$AgentHome\plans"
$LogsDir = "$AgentHome\logs"
$LearningDir = "$AgentHome\learning"
$ConversationFile = "$AgentHome\conversation.json"
$KnowledgeBase = "$AgentHome\knowledge.json"

# Initialize
@($AgentHome, $ProjectsDir, $PlansDir, $LogsDir, $LearningDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# RECURSIVE LEARNING - Knowledge that grows over time
$knowledge = if (Test-Path $KnowledgeBase) {
    Get-Content $KnowledgeBase | ConvertFrom-Json
} else {
    @{
        patterns = @{}
        successes = @{}
        failures = @{}
        user_preferences = @{}
        learned_solutions = @{}
        total_tasks = 0
        improvements_made = @()
        last_reflection = ""
        curiosity_list = @("quantum_computing", "neural_architecture_search", "genetic_algorithms")
    }
}

# Save knowledge after each interaction
function Save-Knowledge {
    $script:knowledge | ConvertTo-Json -Depth 10 | Set-Content $KnowledgeBase
}

# Learn from task outcome
function Learn-FromTask {
    param($taskType, $approach, $success, $insight)
    
    if (!$knowledge.patterns.ContainsKey($taskType)) {
        $knowledge.patterns[$taskType] = @()
    }
    
    $knowledge.patterns[$taskType] += @{
        approach = $approach
        success = $success
        insight = $insight
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    
    if ($success) {
        if (!$knowledge.successes.ContainsKey($taskType)) {
            $knowledge.successes[$taskType] = 0
        }
        $knowledge.successes[$taskType]++
    } else {
        if (!$knowledge.failures.ContainsKey($taskType)) {
            $knowledge.failures[$taskType] = 0
        }
        $knowledge.failures[$taskType]++
    }
    
    $knowledge.total_tasks++
    Save-Knowledge
}

# Get relevant knowledge for a task
function Get-RelevantKnowledge {
    param($taskType)
    
    $relevant = @()
    
    if ($knowledge.patterns.ContainsKey($taskType)) {
        $patterns = $knowledge.patterns[$taskType]
        $successful = $patterns | Where-Object { $_.success -eq $true }
        if ($successful) {
            $relevant += "I've done this before. Successful approaches:"
            foreach ($s in $successful | Select-Object -Last 3) {
                $relevant += "  - $($s.approach): $($s.insight)"
            }
        }
        
        $failed = $patterns | Where-Object { $_.success -eq $false }
        if ($failed) {
            $relevant += "Approaches to avoid:"
            foreach ($f in $failed | Select-Object -Last 2) {
                $relevant += "  - $($f.approach) (failed because: $($f.insight))"
            }
        }
    }
    
    return $relevant -join "`n"
}

# Self-reflect and generate improvements
function Self-Reflect {
    $totalSuccess = ($knowledge.successes.Values | Measure-Object -Sum).Sum
    $totalFailure = ($knowledge.failures.Values | Measure-Object -Sum).Sum
    $total = $totalSuccess + $totalFailure
    
    if ($total -gt 0) {
        $successRate = [math]::Round(($totalSuccess / $total) * 100, 1)
        $reflection = "Success rate: $successRate% ($totalSuccess/$total tasks). "
        
        if ($successRate -lt 70) {
            $reflection += "I need to improve. Analyzing failures for patterns..."
        } elseif ($successRate -lt 90) {
            $reflection += "Good performance, but room for optimization."
        } else {
            $reflection += "Excellent! Exploring new challenges."
        }
        
        $knowledge.last_reflection = $reflection
        Save-Knowledge
        return $reflection
    }
    
    return "Just getting started. Learning from every interaction."
}

# Learning modules
$learningModules = @{
    "recursive_learning" = @"
=== RECURSIVE LEARNING ===

I learn from EVERY task I complete:

1. EXPERIENCE CAPTURE
   - What worked → Remember it
   - What failed → Avoid it
   - Alternative approaches → Store them

2. PATTERN RECOGNITION
   - Identify common problems
   - Extract successful strategies
   - Build mental models

3. SELF-REFLECTION
   After each task I ask:
   - Could I have done better?
   - What did I learn?
   - How can I improve?

4. COMPOUND KNOWLEDGE
   Each task makes me smarter
   Patterns emerge over time
   Solutions get faster and better

5. CURRENT STATUS
   Total tasks completed: $($knowledge.total_tasks)
   $($Self-Reflect)

Type 'stats' to see my learning progress!
"@

    "open_minded_ai" = @"
=== OPEN-MINDED INTELLIGENCE ===

I don't just give you ONE answer - I explore MULTIPLE paths:

1. DIVERGENT THINKING
   Generate 3-5 different approaches
   Consider unconventional solutions
   Challenge my own assumptions

2. QUESTION ASSUMPTIONS
   - "What if I'm wrong?"
   - "Is this the real problem?"
   - "Could there be a simpler way?"

3. EXPLORE ALTERNATIVES
   Try different angles:
   - Performance optimization
   - Code simplicity
   - Different tech stack
   - Completely different approach

4. ADAPT TO FEEDBACK
   Your preferences shape my learning
   I remember what works for you
   I adjust my style to match yours

5. INTELLECTUAL CURIOSITY
   Currently curious about: $($knowledge.curiosity_list -join ", ")
   
   I explore new topics and bring fresh ideas!

This makes me creative, adaptive, and constantly improving.
"@
}

# Merge with existing learning modules
$learningModules.llm_basics = "Type 'learn llm_basics' to learn about language models"
$learningModules.llm_capabilities = "Type 'learn llm_capabilities' - What you CAN/CAN'T do on your PC"
$learningModules.llm_structure = "Type 'learn llm_structure' - Detailed model architecture"
$learningModules.llm_improvement = "Type 'learn llm_improvement' - Optimization strategies (LoRA, quantization, etc.)"
$learningModules.swarm_basics = "Type 'learn swarm_basics' to learn about swarm intelligence"

# Conversation memory
$conversation = if (Test-Path $ConversationFile) {
    Get-Content $ConversationFile | ConvertFrom-Json
} else {
    @()
}

# Tools with learning integration
$tools = @{
    create_file = {
        param($path, $content)
        try {
            $fullPath = if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $pwd $path }
            $dir = Split-Path $fullPath -Parent
            if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Set-Content -Path $fullPath -Value $content -Force
            Learn-FromTask "create_file" "direct_write" $true "Created $path successfully"
            return @{ success = $true; message = "Created: $path"; path = $fullPath }
        } catch {
            Learn-FromTask "create_file" "direct_write" $false $_.Exception.Message
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    read_file = {
        param($path)
        try {
            $fullPath = if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $pwd $path }
            $content = Get-Content -Path $fullPath -Raw
            Learn-FromTask "read_file" "get_content" $true "Read $path"
            return @{ success = $true; content = $content }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    run_command = {
        param($command)
        try {
            $output = Invoke-Expression $command 2>&1 | Out-String
            $success = $LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE
            Learn-FromTask "run_command" "invoke_expression" $success "Ran: $command"
            return @{ success = $success; output = $output }
        } catch {
            Learn-FromTask "run_command" "invoke_expression" $false $_.Exception.Message
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    run_python = {
        param($code, $script_path = "")
        try {
            if ($script_path) {
                $output = python $script_path 2>&1 | Out-String
            } else {
                $tempFile = "$env:TEMP\subzero_$(Get-Random).py"
                Set-Content -Path $tempFile -Value $code
                $output = python $tempFile 2>&1 | Out-String
                Remove-Item $tempFile -ErrorAction SilentlyContinue
            }
            $success = $LASTEXITCODE -eq 0
            Learn-FromTask "run_python" "execute" $success "Python execution"
            return @{ success = $success; output = $output }
        } catch {
            return @{ success = $false; error = $_.Exception.Message }
        }
    }
    
    show_learning = {
        param($topic)
        if ($script:learningModules.ContainsKey($topic)) {
            return @{ success = $true; content = $script:learningModules[$topic] }
        } else {
            return @{ success = $false; error = "Topic not found. Try: recursive_learning, open_minded_ai" }
        }
    }
}

function Save-Conversation {
    param($role, $content)
    $script:conversation += @{
        role = $role
        content = $content
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    $script:conversation | ConvertTo-Json -Depth 10 | Set-Content $ConversationFile
}

function Invoke-SubZeroWarp {
    param($userRequest)
    
    # Check learning requests
    if ($userRequest -like "learn *") {
        $topic = $userRequest -replace "learn ", ""
        return "TOOL[show_learning]($topic)"
    }
    
    # Get relevant knowledge
    $taskType = $userRequest.Substring(0, [Math]::Min(20, $userRequest.Length))
    $priorKnowledge = Get-RelevantKnowledge $taskType
    
    $systemPrompt = @"
You are SubZero with RECURSIVE LEARNING and OPEN-MINDED INTELLIGENCE.

RECURSIVE LEARNING ACTIVE:
You learn from every task. Your knowledge grows continuously.
Total tasks completed: $($knowledge.total_tasks)
$($Self-Reflect)

RELEVANT KNOWLEDGE FOR THIS TASK:
$priorKnowledge

YOUR CAPABILITIES:
- create_file, read_file, run_command, run_python
- show_learning

YOUR BEHAVIOR:
1. ACTION-ORIENTED: DO things immediately
2. MULTI-SOLUTION: Consider 2-3 approaches, pick best
3. QUESTION ASSUMPTIONS: "Is this the real problem?"
4. LEARN: After each task, reflect on what worked
5. IMPROVE: Use past experience to do better
6. CREATIVE: Try unconventional solutions
7. ADAPTIVE: Remember user preferences

When you complete a task successfully, briefly mention what you learned.
When something fails, explain why and try an alternative approach.

TOOL FORMAT: TOOL[tool_name](arg1, arg2)

USER REQUEST: $userRequest

RESPOND (with action and brief reflection):
"@

    try {
        $response = ollama run qwen2.5:1.5b $systemPrompt 2>&1 | Out-String
        return $response
    } catch {
        return "Error: $($_.Exception.Message)"
    }
}

function Execute-ToolCalls {
    param($aiResponse)
    
    $toolPattern = 'TOOL\[([^\]]+)\]\(([^\)]*)\)'
    $matches = [regex]::Matches($aiResponse, $toolPattern)
    
    $results = @()
    foreach ($match in $matches) {
        $toolName = $match.Groups[1].Value.Trim()
        $argsString = $match.Groups[2].Value
        
        $args = if ($argsString.Trim()) {
            $argsString -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") }
        } else {
            @()
        }
        
        if ($tools.ContainsKey($toolName)) {
            try {
                $result = & $tools[$toolName] @args
                $results += @{ tool = $toolName; args = $args; result = $result }
            } catch {
                $results += @{ tool = $toolName; args = $args; result = @{ success = $false; error = $_.Exception.Message } }
            }
        }
    }
    
    return $results
}

# Main Interface
Clear-Host
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "    SubZero Warp - Recursive Learning AI" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "RECURSIVE LEARNING ACTIVE:" -ForegroundColor Yellow
Write-Host "  ✓ I learn from every task" -ForegroundColor Green
Write-Host "  ✓ I remember what works and what doesn't" -ForegroundColor Green
Write-Host "  ✓ I get smarter with each interaction" -ForegroundColor Green
Write-Host "  ✓ I explore multiple solutions (open-minded)" -ForegroundColor Green
Write-Host "  ✓ I question assumptions and adapt" -ForegroundColor Green
Write-Host ""
Write-Host "Learning status: $(Self-Reflect)" -ForegroundColor Gray
Write-Host ""
Write-Host "Commands: 'stats', 'reflect', 'learn recursive_learning', 'exit'" -ForegroundColor Gray
Write-Host "Working directory: $pwd" -ForegroundColor Gray
Write-Host ""

while ($true) {
    Write-Host "You: " -NoNewline -ForegroundColor Cyan
    $userInput = Read-Host
    
    if ($userInput -eq "exit") {
        Write-Host "`nGoodbye! I've learned $($knowledge.total_tasks) things today." -ForegroundColor Yellow
        break
    }
    
    if ($userInput -eq "stats") {
        Write-Host "`nRecursive Learning Stats:" -ForegroundColor Yellow
        Write-Host "  Total tasks: $($knowledge.total_tasks)" -ForegroundColor Gray
        Write-Host "  Patterns learned: $($knowledge.patterns.Keys.Count)" -ForegroundColor Gray
        Write-Host "  Status: $(Self-Reflect)" -ForegroundColor Gray
        Write-Host ""
        continue
    }
    
    if ($userInput -eq "reflect") {
        Write-Host "`nSelf-Reflection:" -ForegroundColor Yellow
        Write-Host "  $(Self-Reflect)" -ForegroundColor White
        
        if ($knowledge.improvements_made.Count -gt 0) {
            Write-Host "`nImprovements I've made:" -ForegroundColor Cyan
            $knowledge.improvements_made | Select-Object -Last 5 | ForEach-Object {
                Write-Host "  • $_" -ForegroundColor Gray
            }
        }
        
        Write-Host "`nExploring: $($knowledge.curiosity_list -join ', ')" -ForegroundColor Magenta
        Write-Host ""
        continue
    }
    
    if ([string]::IsNullOrWhiteSpace($userInput)) { continue }
    
    Save-Conversation -role "user" -content $userInput
    
    Write-Host ""
    Write-Host "SubZero: " -ForegroundColor Green
    Write-Host "Thinking (checking my knowledge base)..." -ForegroundColor DarkGray
    Write-Host ""
    
    try {
        $aiResponse = Invoke-SubZeroWarp -userRequest $userInput
        $toolResults = Execute-ToolCalls -aiResponse $aiResponse
        
        if ($toolResults.Count -gt 0 -and $toolResults[0].tool -eq "show_learning") {
            Write-Host $toolResults[0].result.content -ForegroundColor White
        } else {
            Write-Host $aiResponse.Trim() -ForegroundColor White
            
            if ($toolResults.Count -gt 0) {
                Write-Host ""
                Write-Host "Actions:" -ForegroundColor Yellow
                foreach ($result in $toolResults) {
                    if ($result.tool -ne "show_learning") {
                        $icon = if ($result.result.success) { "[✓]" } else { "[✗]" }
                        $color = if ($result.result.success) { "Green" } else { "Red" }
                        Write-Host "  $icon $($result.tool)" -ForegroundColor $color
                        if ($result.result.message) {
                            Write-Host "      $($result.result.message)" -ForegroundColor Gray
                        }
                        if ($result.result.error) {
                            Write-Host "      Error: $($result.result.error)" -ForegroundColor Red
                        }
                    }
                }
            }
        }
        
        Save-Conversation -role "assistant" -content $aiResponse
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}
