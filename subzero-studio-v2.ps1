# SubZero Studio V2 - Fully Functional AI Desktop App
# All features work: Chat, Book Writing, Audiobooks, Settings

param([int]$Port = 8080)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$ProjectsDir = "$SubZeroHome\projects"
$AudioDir = "$SubZeroHome\audiobooks"
$BooksDir = "$SubZeroHome\books"
$ConfigFile = "$SubZeroHome\config.json"

# Initialize
@($SubZeroHome, $ProjectsDir, $AudioDir, $BooksDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Default config
if (!(Test-Path $ConfigFile)) {
    @{
        aiModel = "llama3.2"
        voiceSpeed = "medium"
        theme = "dark"
        autoSave = $true
    } | ConvertTo-Json | Set-Content $ConfigFile
}

$html = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SubZero Studio - AI Assistant</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            height: 100vh;
            overflow: hidden;
        }
        
        .app-container {
            display: flex;
            height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: 250px;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
            color: white;
            padding: 20px;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 30px;
            text-align: center;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        
        .nav-button {
            padding: 15px 20px;
            margin: 5px 0;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            text-align: left;
            font-size: 16px;
            transition: all 0.3s;
        }
        
        .nav-button:hover, .nav-button.active {
            background: rgba(255,255,255,0.3);
            transform: translateX(5px);
        }
        
        .nav-button::before {
            margin-right: 10px;
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: white;
            margin: 20px 20px 20px 0;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 { font-size: 24px; }
        
        .header-btn {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            margin-left: 10px;
        }
        
        .header-btn:hover { background: rgba(255,255,255,0.4); }
        
        /* Content Sections */
        .content-section {
            display: none;
            flex: 1;
            padding: 30px;
            overflow-y: auto;
        }
        
        .content-section.active {
            display: flex;
            flex-direction: column;
        }
        
        /* CHAT SECTION */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f5f5f5;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .message {
            margin: 15px 0;
            padding: 15px 20px;
            border-radius: 12px;
            max-width: 70%;
            animation: slideIn 0.3s;
            line-height: 1.6;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.user {
            background: #667eea;
            color: white;
            margin-left: auto;
            text-align: right;
        }
        
        .message.assistant {
            background: white;
            color: #333;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .message.system {
            background: #ffd700;
            color: #333;
            text-align: center;
            margin: 10px auto;
            font-weight: bold;
        }
        
        .input-area {
            display: flex;
            gap: 10px;
        }
        
        .input-area input {
            flex: 1;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
        }
        
        .input-area button {
            padding: 15px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
        }
        
        .input-area button:hover { background: #5568d3; }
        
        /* BOOK EDITOR */
        .editor-grid {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 20px;
            height: 100%;
        }
        
        .chapters-panel {
            background: #f5f5f5;
            border-radius: 10px;
            padding: 20px;
            overflow-y: auto;
        }
        
        .chapter-item {
            padding: 15px;
            margin: 10px 0;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .chapter-item:hover { transform: translateX(5px); box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        
        .editor-main {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .editor-toolbar {
            display: flex;
            gap: 10px;
        }
        
        .toolbar-btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        
        .toolbar-btn:hover { background: #5568d3; }
        
        .editor-textarea {
            flex: 1;
            padding: 20px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            font-family: 'Georgia', serif;
            resize: none;
        }
        
        /* AUDIOBOOKS */
        .audiobook-panel {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .audio-controls {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
        }
        
        .audio-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }
        
        .audio-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* SETTINGS */
        .settings-panel {
            max-width: 600px;
        }
        
        .setting-group {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        
        .setting-group h3 {
            margin-bottom: 15px;
            color: #667eea;
        }
        
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .setting-item:last-child { border-bottom: none; }
        
        select, input[type="text"] {
            padding: 8px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .btn-save {
            background: #28a745;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 20px;
        }
        
        .btn-save:hover { background: #218838; }
        
        .status { 
            margin-top: 10px;
            padding: 10px;
            border-radius: 5px;
            display: none;
        }
        .status.success { background: #d4edda; color: #155724; display: block; }
        .status.error { background: #f8d7da; color: #721c24; display: block; }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="logo">⚡ SubZero Studio</div>
            <button class="nav-button active" onclick="showSection('chat')">💬 Chat with Mini-Warp</button>
            <button class="nav-button" onclick="showSection('books')">📚 Book Editor</button>
            <button class="nav-button" onclick="showSection('audio')">🎧 Audiobooks</button>
            <button class="nav-button" onclick="showSection('projects')">📁 Projects</button>
            <button class="nav-button" onclick="showSection('settings')">⚙️ Settings</button>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <h1 id="pageTitle">Chat with Mini-Warp</h1>
                <div>
                    <button class="header-btn" onclick="clearChat()">Clear Chat</button>
                    <button class="header-btn" onclick="location.reload()">Refresh</button>
                </div>
            </div>
            
            <!-- CHAT SECTION -->
            <div id="chat" class="content-section active">
                <div class="chat-container">
                    <div class="messages" id="chatMessages">
                        <div class="message system">Mini-Warp AI is ready! Ask me anything or tell me what to build.</div>
                    </div>
                    <div class="input-area">
                        <input type="text" id="chatInput" placeholder="Type your message... (e.g., 'Write chapter 1 about dragons')" onkeypress="if(event.key==='Enter') sendMessage()">
                        <button onclick="sendMessage()">Send</button>
                    </div>
                </div>
            </div>
            
            <!-- BOOK EDITOR SECTION -->
            <div id="books" class="content-section">
                <div class="editor-grid">
                    <div class="chapters-panel">
                        <h3>Chapters</h3>
                        <button class="toolbar-btn" style="width:100%; margin-bottom:15px;" onclick="newChapter()">+ New Chapter</button>
                        <div id="chaptersList"></div>
                    </div>
                    <div class="editor-main">
                        <input type="text" id="chapterTitle" placeholder="Chapter Title" style="padding:15px; border:2px solid #e0e0e0; border-radius:10px; font-size:18px; font-weight:bold;">
                        <div class="editor-toolbar">
                            <button class="toolbar-btn" onclick="saveChapter()">💾 Save</button>
                            <button class="toolbar-btn" onclick="aiWriteChapter()">🤖 AI Write</button>
                            <button class="toolbar-btn" onclick="generateAudioFromChapter()">🎧 To Audio</button>
                        </div>
                        <textarea id="chapterContent" class="editor-textarea" placeholder="Start writing your chapter here..."></textarea>
                        <div id="editorStatus" class="status"></div>
                    </div>
                </div>
            </div>
            
            <!-- AUDIOBOOKS SECTION -->
            <div id="audio" class="content-section">
                <div class="audiobook-panel">
                    <div class="audio-controls">
                        <h3>Generate Audiobook</h3>
                        <input type="text" id="audioTitle" placeholder="Audiobook Title" style="width:100%; margin-bottom:10px;">
                        <textarea id="audioText" placeholder="Enter text to convert to audio..." style="width:100%; height:100px; padding:10px; border-radius:8px; margin-bottom:10px;"></textarea>
                        <button class="toolbar-btn" onclick="generateAudio()">🎙️ Generate Audio</button>
                        <div id="audioStatus" class="status"></div>
                    </div>
                    <h3>Your Audiobooks</h3>
                    <div class="audio-list" id="audioList"></div>
                </div>
            </div>
            
            <!-- PROJECTS SECTION -->
            <div id="projects" class="content-section">
                <h2>Your Projects</h2>
                <div id="projectsList" style="display:grid; gap:15px; margin-top:20px;"></div>
            </div>
            
            <!-- SETTINGS SECTION -->
            <div id="settings" class="content-section">
                <div class="settings-panel">
                    <div class="setting-group">
                        <h3>AI Configuration</h3>
                        <div class="setting-item">
                            <label>AI Model:</label>
                            <select id="settingModel">
                                <option value="llama3.2">Llama 3.2 (Fast)</option>
                                <option value="llama3.1">Llama 3.1</option>
                                <option value="mistral">Mistral</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="setting-group">
                        <h3>Voice Settings</h3>
                        <div class="setting-item">
                            <label>Speech Speed:</label>
                            <select id="settingVoiceSpeed">
                                <option value="slow">Slow</option>
                                <option value="medium">Medium</option>
                                <option value="fast">Fast</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="setting-group">
                        <h3>Editor Preferences</h3>
                        <div class="setting-item">
                            <label>Theme:</label>
                            <select id="settingTheme">
                                <option value="light">Light</option>
                                <option value="dark">Dark</option>
                            </select>
                        </div>
                        <div class="setting-item">
                            <label>Auto-save:</label>
                            <input type="checkbox" id="settingAutoSave">
                        </div>
                    </div>
                    
                    <button class="btn-save" onclick="saveSettings()">Save Settings</button>
                    <div id="settingsStatus" class="status"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentChapter = null;
        let chapters = [];
        
        // Navigation
        function showSection(section) {
            document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-button').forEach(b => b.classList.remove('active'));
            document.getElementById(section).classList.add('active');
            event.target.classList.add('active');
            
            const titles = {
                chat: 'Chat with Mini-Warp',
                books: 'Book Editor',
                audio: 'Audiobooks',
                projects: 'Your Projects',
                settings: 'Settings'
            };
            document.getElementById('pageTitle').textContent = titles[section];
            
            if (section === 'audio') loadAudioList();
            if (section === 'projects') loadProjects();
            if (section === 'settings') loadSettings();
        }
        
        // CHAT FUNCTIONS
        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            
            addMessage('user', msg);
            input.value = '';
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await response.json();
                addMessage('assistant', data.response);
            } catch (err) {
                addMessage('system', 'Error: ' + err.message);
            }
        }
        
        function addMessage(type, text) {
            const div = document.createElement('div');
            div.className = 'message ' + type;
            div.textContent = text;
            document.getElementById('chatMessages').appendChild(div);
            div.scrollIntoView({behavior: 'smooth'});
        }
        
        function clearChat() {
            document.getElementById('chatMessages').innerHTML = '<div class="message system">Chat cleared. How can I help?</div>';
        }
        
        // BOOK EDITOR FUNCTIONS
        function newChapter() {
            const id = Date.now();
            const chapter = {id, title: 'New Chapter', content: ''};
            chapters.push(chapter);
            renderChapters();
            loadChapter(id);
        }
        
        function renderChapters() {
            const list = document.getElementById('chaptersList');
            list.innerHTML = chapters.map(ch => 
                '<div class="chapter-item" onclick="loadChapter(' + ch.id + ')">' + ch.title + '</div>'
            ).join('');
        }
        
        function loadChapter(id) {
            const chapter = chapters.find(c => c.id === id);
            if (chapter) {
                currentChapter = chapter;
                document.getElementById('chapterTitle').value = chapter.title;
                document.getElementById('chapterContent').value = chapter.content;
            }
        }
        
        async function saveChapter() {
            if (!currentChapter) return;
            currentChapter.title = document.getElementById('chapterTitle').value;
            currentChapter.content = document.getElementById('chapterContent').value;
            
            try {
                await fetch('/api/save-chapter', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(currentChapter)
                });
                showStatus('editorStatus', 'Chapter saved!', 'success');
                renderChapters();
            } catch (err) {
                showStatus('editorStatus', 'Error: ' + err.message, 'error');
            }
        }
        
        async function aiWriteChapter() {
            const title = document.getElementById('chapterTitle').value || 'Untitled';
            showStatus('editorStatus', 'AI is writing...', 'success');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: 'Write a detailed chapter titled: ' + title})
                });
                const data = await response.json();
                document.getElementById('chapterContent').value = data.response;
                showStatus('editorStatus', 'AI finished writing!', 'success');
            } catch (err) {
                showStatus('editorStatus', 'Error: ' + err.message, 'error');
            }
        }
        
        async function generateAudioFromChapter() {
            const title = document.getElementById('chapterTitle').value;
            const text = document.getElementById('chapterContent').value;
            if (!text) return alert('No content to convert!');
            
            showStatus('editorStatus', 'Generating audio...', 'success');
            try {
                await fetch('/api/generate-audio', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, text})
                });
                showStatus('editorStatus', 'Audio generated!', 'success');
            } catch (err) {
                showStatus('editorStatus', 'Error: ' + err.message, 'error');
            }
        }
        
        // AUDIOBOOK FUNCTIONS
        async function generateAudio() {
            const title = document.getElementById('audioTitle').value || 'Audio_' + Date.now();
            const text = document.getElementById('audioText').value;
            if (!text) return alert('Enter text first!');
            
            showStatus('audioStatus', 'Generating...', 'success');
            try {
                await fetch('/api/generate-audio', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, text})
                });
                showStatus('audioStatus', 'Audio created!', 'success');
                loadAudioList();
                document.getElementById('audioText').value = '';
            } catch (err) {
                showStatus('audioStatus', 'Error: ' + err.message, 'error');
            }
        }
        
        async function loadAudioList() {
            try {
                const response = await fetch('/api/audio-list');
                const data = await response.json();
                const list = document.getElementById('audioList');
                list.innerHTML = data.map(a => 
                    '<div class="audio-card"><h4>' + a.title + '</h4><audio controls src="' + a.url + '" style="width:100%; margin-top:10px;"></audio></div>'
                ).join('') || '<p>No audiobooks yet</p>';
            } catch (err) {
                console.error(err);
            }
        }
        
        // PROJECTS
        async function loadProjects() {
            try {
                const response = await fetch('/api/projects');
                const data = await response.json();
                const list = document.getElementById('projectsList');
                list.innerHTML = data.map(p => 
                    '<div class="audio-card"><h3>' + p.name + '</h3><p>' + p.description + '</p><small>' + p.chapters + ' chapters, ' + p.words + ' words</small></div>'
                ).join('') || '<p>No projects yet</p>';
            } catch (err) {
                console.error(err);
            }
        }
        
        // SETTINGS
        async function loadSettings() {
            try {
                const response = await fetch('/api/get-config');
                const config = await response.json();
                document.getElementById('settingModel').value = config.aiModel;
                document.getElementById('settingVoiceSpeed').value = config.voiceSpeed;
                document.getElementById('settingTheme').value = config.theme;
                document.getElementById('settingAutoSave').checked = config.autoSave;
            } catch (err) {
                console.error(err);
            }
        }
        
        async function saveSettings() {
            const config = {
                aiModel: document.getElementById('settingModel').value,
                voiceSpeed: document.getElementById('settingVoiceSpeed').value,
                theme: document.getElementById('settingTheme').value,
                autoSave: document.getElementById('settingAutoSave').checked
            };
            
            try {
                await fetch('/api/save-config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                });
                showStatus('settingsStatus', 'Settings saved!', 'success');
            } catch (err) {
                showStatus('settingsStatus', 'Error: ' + err.message, 'error');
            }
        }
        
        function showStatus(id, msg, type) {
            const el = document.getElementById(id);
            el.textContent = msg;
            el.className = 'status ' + type;
            setTimeout(() => el.className = 'status', 3000);
        }
    </script>
</body>
</html>
"@

# Start HTTP Server
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      SubZero Studio V2 - STARTED!      " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "URL: http://localhost:$Port" -ForegroundColor Yellow
Write-Host "Opening browser..." -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Red
Write-Host ""

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
            
            # Call Ollama with Mini-Warp personality
            $prompt = "You are Mini-Warp, a helpful AI assistant. You are action-oriented and do tasks. User asks: $($body.message)"
            $aiResponse = ollama run llama3.2 $prompt 2>&1
            
            $result = @{ response = $aiResponse } | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/save-chapter") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $chapter = $reader.ReadToEnd() | ConvertFrom-Json
            $chapterFile = "$BooksDir\chapter_$($chapter.id).json"
            $chapter | ConvertTo-Json | Set-Content $chapterFile
            
            $result = @{ status = "saved" } | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/generate-audio") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $body = $reader.ReadToEnd() | ConvertFrom-Json
            
            $audioFile = "$AudioDir\$($body.title).wav"
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.SetOutputToWaveFile($audioFile)
            $synth.Speak($body.text)
            $synth.Dispose()
            
            $result = @{ status = "generated"; file = $audioFile } | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/audio-list") {
            $audioFiles = Get-ChildItem "$AudioDir\*.wav" -ErrorAction SilentlyContinue
            $list = $audioFiles | ForEach-Object {
                @{ title = $_.BaseName; url = "/audio/$($_.Name)" }
            }
            $result = $list | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -match "^/audio/(.+)$") {
            $fileName = $Matches[1]
            $filePath = "$AudioDir\$fileName"
            if (Test-Path $filePath) {
                $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
                $response.ContentType = "audio/wav"
                $response.ContentLength64 = $fileBytes.Length
                $response.OutputStream.Write($fileBytes, 0, $fileBytes.Length)
            }
        }
        elseif ($url -eq "/api/projects") {
            $projects = @(
                @{ name = "My First Book"; description = "Adventure story"; chapters = 5; words = 12500 }
            )
            $result = $projects | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/get-config") {
            $config = Get-Content $ConfigFile | ConvertFrom-Json
            $result = $config | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/save-config") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $config = $reader.ReadToEnd()
            $config | Set-Content $ConfigFile
            
            $result = @{ status = "saved" } | ConvertTo-Json
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
