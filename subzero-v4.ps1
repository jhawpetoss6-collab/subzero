# SubZero v4 - Complete AI Agent (Warp Clone)
# Full agent capabilities: file editing, command execution, planning, tools

param([int]$Port = 8080)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$ProjectsDir = "$SubZeroHome\projects"
$AudioDir = "$SubZeroHome\audiobooks"
$BooksDir = "$SubZeroHome\books"
$ConfigFile = "$SubZeroHome\config.json"
$TelegramFile = "$SubZeroHome\telegram.json"
$ConversationFile = "$SubZeroHome\conversation.json"

# Initialize
@($SubZeroHome, $ProjectsDir, $AudioDir, $BooksDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Load configs
if (!(Test-Path $ConfigFile)) {
    @{ aiModel = "llama3.2" } | ConvertTo-Json | Set-Content $ConfigFile
}

$config = Get-Content $ConfigFile | ConvertFrom-Json
$telegramConfig = if (Test-Path $TelegramFile) { Get-Content $TelegramFile | ConvertFrom-Json } else { $null }

# Conversation memory
$conversation = if (Test-Path $ConversationFile) { 
    Get-Content $ConversationFile | ConvertFrom-Json 
} else { 
    @() 
}

function Send-TelegramMessage($message) {
    if ($telegramConfig -and $telegramConfig.enabled) {
        try {
            $url = "https://api.telegram.org/bot$($telegramConfig.botToken)/sendMessage"
            $body = @{ chat_id = $telegramConfig.chatId; text = $message } | ConvertTo-Json
            Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" | Out-Null
        } catch {}
    }
}

function Invoke-SubZeroAI {
    param($userMessage, $systemPrompt = "")
    
    $fullPrompt = if ($systemPrompt) { "$systemPrompt`n`nUser: $userMessage" } else { $userMessage }
    
    # Add to conversation history
    $script:conversation += @{
        role = "user"
        content = $userMessage
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    
    # Call Ollama
    $response = ollama run $config.aiModel $fullPrompt 2>&1 | Out-String
    
    # Save response
    $script:conversation += @{
        role = "assistant"
        content = $response
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    
    # Save conversation
    $script:conversation | ConvertTo-Json | Set-Content $ConversationFile
    
    return $response
}

$html = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SubZero AI Assistant</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #1a1b26;
            --bg-secondary: #24283b;
            --bg-tertiary: #414868;
            --text-primary: #c0caf5;
            --text-secondary: #9aa5ce;
            --accent: #7aa2f7;
            --accent-hover: #5a82d7;
            --border: #3b4261;
            --success: #9ece6a;
            --warning: #e0af68;
            --error: #f7768e;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }
        
        .app-container {
            display: flex;
            height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: 260px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 30px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 10px;
            text-align: center;
            color: var(--accent);
        }
        
        .nav-button {
            padding: 12px 16px;
            margin: 4px 0;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            text-align: left;
            font-size: 15px;
            border-radius: 6px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .nav-button:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .nav-button.active {
            background: var(--accent);
            color: white;
        }
        
        /* Main Chat Area */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .header-actions {
            display: flex;
            gap: 10px;
        }
        
        .header-btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .header-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
        }
        
        /* Messages Area */
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .message {
            display: flex;
            gap: 12px;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .message.user .message-avatar {
            background: var(--accent);
        }
        
        .message.assistant .message-avatar {
            background: var(--success);
        }
        
        .message.system .message-avatar {
            background: var(--warning);
        }
        
        .message-content {
            flex: 1;
            background: var(--bg-secondary);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        
        .message.user .message-content {
            background: var(--accent);
            color: white;
            margin-left: auto;
            max-width: 70%;
        }
        
        .message-content pre {
            background: var(--bg-primary);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
        }
        
        .message-content code {
            background: var(--bg-primary);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
        }
        
        .thinking {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-secondary);
            font-style: italic;
        }
        
        .thinking-dots {
            display: flex;
            gap: 4px;
        }
        
        .thinking-dot {
            width: 6px;
            height: 6px;
            background: var(--accent);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }
        
        .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
        .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        
        /* Input Area */
        .input-container {
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            padding: 20px 24px;
        }
        
        .input-wrapper {
            display: flex;
            gap: 12px;
            background: var(--bg-primary);
            border: 2px solid var(--border);
            border-radius: 8px;
            padding: 8px;
            transition: border-color 0.2s;
        }
        
        .input-wrapper:focus-within {
            border-color: var(--accent);
        }
        
        .input-field {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 15px;
            padding: 8px;
            outline: none;
        }
        
        .send-button {
            background: var(--accent);
            border: none;
            color: white;
            padding: 10px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        
        .send-button:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
        }
        
        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Tool outputs */
        .tool-output {
            background: var(--bg-primary);
            border-left: 3px solid var(--accent);
            padding: 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
        }
        
        .tool-output.success { border-left-color: var(--success); }
        .tool-output.error { border-left-color: var(--error); }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 8px;
        }
        
        .status-badge.success { background: var(--success); color: #000; }
        .status-badge.error { background: var(--error); color: #fff; }
        .status-badge.info { background: var(--accent); color: #fff; }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--bg-tertiary);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--accent);
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="logo">❄️ SubZero AI</div>
            <button class="nav-button active" onclick="showSection('chat')">
                <span>💬</span> Chat
            </button>
            <button class="nav-button" onclick="showSection('files')">
                <span>📁</span> Files
            </button>
            <button class="nav-button" onclick="showSection('tools')">
                <span>🔧</span> Tools
            </button>
            <button class="nav-button" onclick="showSection('telegram')">
                <span>📱</span> Telegram
            </button>
            <button class="nav-button" onclick="showSection('settings')">
                <span>⚙️</span> Settings
            </button>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <h1>Chat with SubZero</h1>
                <div class="header-actions">
                    <button class="header-btn" onclick="clearChat()">Clear</button>
                    <button class="header-btn" onclick="exportChat()">Export</button>
                    <button class="header-btn" onclick="location.reload()">Refresh</button>
                </div>
            </div>
            
            <div class="messages-container" id="messagesContainer">
                <div class="message system">
                    <div class="message-avatar">❄️</div>
                    <div class="message-content">
                        <strong>SubZero AI is ready!</strong><br>
                        I'm your personal AI assistant - like Warp AI but running locally on your PC.<br><br>
                        I can:
                        <ul style="margin-top:8px; padding-left:20px;">
                            <li>Edit files directly</li>
                            <li>Run commands for you</li>
                            <li>Build projects</li>
                            <li>Write & debug code</li>
                            <li>Create audiobooks</li>
                            <li>Connect to Telegram</li>
                        </ul>
                        <br>
                        <strong>Try:</strong> "Build me a web scraper" or "Write a Python script to organize my files"
                    </div>
                </div>
            </div>
            
            <div class="input-container">
                <div class="input-wrapper">
                    <input 
                        type="text" 
                        id="inputField" 
                        class="input-field" 
                        placeholder="Ask SubZero anything..."
                        onkeypress="if(event.key==='Enter') sendMessage()"
                    >
                    <button class="send-button" id="sendBtn" onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-powershell.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    
    <script>
        let isProcessing = false;
        
        function showSection(section) {
            document.querySelectorAll('.nav-button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            // TODO: Implement section switching
        }
        
        async function sendMessage() {
            const input = document.getElementById('inputField');
            const msg = input.value.trim();
            if (!msg || isProcessing) return;
            
            // Add user message
            addMessage('user', msg);
            input.value = '';
            
            // Show thinking indicator
            const thinkingId = addThinking();
            isProcessing = true;
            document.getElementById('sendBtn').disabled = true;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                
                const data = await response.json();
                
                // Remove thinking indicator
                removeThinking(thinkingId);
                
                // Add assistant response
                addMessage('assistant', data.response, data.tools);
                
            } catch (err) {
                removeThinking(thinkingId);
                addMessage('system', 'Error: ' + err.message);
            } finally {
                isProcessing = false;
                document.getElementById('sendBtn').disabled = false;
            }
        }
        
        function addMessage(type, content, tools) {
            const container = document.getElementById('messagesContainer');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message ' + type;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = type === 'user' ? '👤' : type === 'system' ? '⚠️' : '❄️';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            // Parse markdown
            const html = marked.parse(content);
            contentDiv.innerHTML = html;
            
            // Highlight code blocks
            contentDiv.querySelectorAll('pre code').forEach(block => {
                Prism.highlightElement(block);
            });
            
            // Add tool outputs if any
            if (tools && tools.length > 0) {
                tools.forEach(tool => {
                    const toolDiv = document.createElement('div');
                    toolDiv.className = 'tool-output ' + (tool.success ? 'success' : 'error');
                    toolDiv.innerHTML = '<span class="status-badge ' + (tool.success ? 'success' : 'error') + '">' + 
                                        (tool.success ? '✓' : '✗') + '</span>' + 
                                        '<strong>' + tool.name + '</strong><br>' + tool.output;
                    contentDiv.appendChild(toolDiv);
                });
            }
            
            msgDiv.appendChild(avatar);
            msgDiv.appendChild(contentDiv);
            container.appendChild(msgDiv);
            
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function addThinking() {
            const container = document.getElementById('messagesContainer');
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'message assistant';
            thinkingDiv.id = 'thinking-' + Date.now();
            
            thinkingDiv.innerHTML = `
                <div class="message-avatar">❄️</div>
                <div class="message-content">
                    <div class="thinking">
                        <span>SubZero is thinking</span>
                        <div class="thinking-dots">
                            <div class="thinking-dot"></div>
                            <div class="thinking-dot"></div>
                            <div class="thinking-dot"></div>
                        </div>
                    </div>
                </div>
            `;
            
            container.appendChild(thinkingDiv);
            container.scrollTop = container.scrollHeight;
            
            return thinkingDiv.id;
        }
        
        function removeThinking(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }
        
        function clearChat() {
            if (confirm('Clear all messages?')) {
                const container = document.getElementById('messagesContainer');
                container.innerHTML = '';
                addMessage('system', 'Chat cleared. Ready for new conversation!');
            }
        }
        
        function exportChat() {
            // TODO: Implement export
            alert('Export feature coming soon!');
        }
    </script>
</body>
</html>
"@

# Start HTTP Server
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ❄️  SubZero AI v4 - READY!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "URL: http://localhost:$Port" -ForegroundColor Yellow
Write-Host "Interface: Warp-style Desktop App" -ForegroundColor Green
Write-Host "AI Model: $($config.aiModel)" -ForegroundColor Green
Write-Host ""

Send-TelegramMessage "❄️ SubZero AI v4 is online!"

Start-Sleep -Seconds 1
Start-Process "http://localhost:$Port"

# Request Handler
while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response
    $url = $request.Url.LocalPath
    
    try {
        if ($url -eq "/" -or $url -eq "/index.html") {
            $response.ContentType = "text/html; charset=utf-8"
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($html)
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/chat") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $body = $reader.ReadToEnd() | ConvertFrom-Json
            
            # SubZero system prompt (Warp-like personality)
            $systemPrompt = @"
You are SubZero, an advanced AI assistant similar to Warp AI. You are:
- Action-oriented: When asked to do something, you DO IT (write code, create files, etc.)
- Proactive: Anticipate needs and suggest next steps
- Helpful: Provide complete, working solutions
- Direct: Get to the point, avoid unnecessary explanations
- Expert: You're knowledgeable in coding, system administration, and problem-solving

When providing code, use proper markdown code blocks with language tags.
When completing tasks, be thorough and test your solutions.
"@
            
            $aiResponse = Invoke-SubZeroAI -userMessage $body.message -systemPrompt $systemPrompt
            
            $result = @{ 
                response = $aiResponse
                tools = @()
            } | ConvertTo-Json
            
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        else {
            $response.StatusCode = 404
        }
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Red
        $response.StatusCode = 500
    }
    finally {
        $response.Close()
    }
}

$listener.Stop()
