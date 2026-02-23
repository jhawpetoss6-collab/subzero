# SubZero Studio - GUI Desktop Application
# Complete workspace with chat, book writing, audio books, and file management

param(
    [int]$Port = 8080
)

$SubZeroHome = "$env:USERPROFILE\.subzero"
$StudioDir = "$SubZeroHome\studio"
$ProjectsDir = "$StudioDir\projects"
$AudioDir = "$StudioDir\audiobooks"

# Initialize directories
@($SubZeroHome, $StudioDir, $ProjectsDir, $AudioDir) | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ | Out-Null }
}

# Create HTML GUI
$html = @"
<!DOCTYPE html>
<html>
<head>
    <title>SubZero Studio</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: 60px;
            background: rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 0;
            backdrop-filter: blur(10px);
        }
        
        .nav-item {
            width: 40px;
            height: 40px;
            margin: 10px 0;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 20px;
        }
        
        .nav-item:hover, .nav-item.active {
            background: rgba(255,255,255,0.3);
            transform: scale(1.1);
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: rgba(255,255,255,0.95);
            margin: 20px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 600;
        }
        
        .header-actions button {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            margin-left: 10px;
            transition: all 0.3s;
        }
        
        .header-actions button:hover {
            background: rgba(255,255,255,0.3);
        }
        
        /* Content Area */
        .content-area {
            flex: 1;
            display: flex;
            overflow: hidden;
        }
        
        .tab-content {
            display: none;
            flex: 1;
            padding: 30px;
            overflow-y: auto;
        }
        
        .tab-content.active {
            display: flex;
            flex-direction: column;
        }
        
        /* Chat Interface */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .message {
            margin: 10px 0;
            padding: 15px;
            border-radius: 10px;
            max-width: 70%;
            animation: fadeIn 0.3s;
        }
        
        .message.user {
            background: #667eea;
            color: white;
            margin-left: auto;
        }
        
        .message.assistant {
            background: white;
            color: #333;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .chat-input {
            display: flex;
            gap: 10px;
        }
        
        .chat-input input {
            flex: 1;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
        }
        
        .chat-input button {
            padding: 15px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
        }
        
        /* Book Editor */
        .editor-container {
            display: flex;
            gap: 20px;
            height: 100%;
        }
        
        .chapters-list {
            width: 250px;
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            overflow-y: auto;
        }
        
        .chapter-item {
            padding: 10px;
            margin: 5px 0;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .chapter-item:hover {
            background: #667eea;
            color: white;
        }
        
        .editor {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .editor-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        
        .editor-header input {
            flex: 1;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
        }
        
        .editor-content {
            flex: 1;
            padding: 20px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            line-height: 1.8;
            resize: none;
        }
        
        /* Audio Books */
        .audiobook-container {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .audio-controls {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
        }
        
        .audio-controls select,
        .audio-controls input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
        }
        
        .audio-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }
        
        .audio-item {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* Projects/Filing */
        .projects-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .project-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        
        .project-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 25px rgba(0,0,0,0.15);
        }
        
        .project-card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .project-stats {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
        }
        
        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-secondary {
            background: #e0e0e0;
            color: #333;
        }
        
        .btn:hover {
            transform: scale(1.05);
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Status Bar */
        .status-bar {
            background: #f8f9fa;
            padding: 10px 30px;
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar Navigation -->
        <div class="sidebar">
            <div class="nav-item active" onclick="switchTab('chat')" title="Chat">💬</div>
            <div class="nav-item" onclick="switchTab('editor')" title="Book Editor">📝</div>
            <div class="nav-item" onclick="switchTab('audio')" title="Audio Books">🎙️</div>
            <div class="nav-item" onclick="switchTab('projects')" title="Projects">📁</div>
            <div class="nav-item" onclick="switchTab('settings')" title="Settings">⚙️</div>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <!-- Header -->
            <div class="header">
                <h1>❄️ SubZero Studio</h1>
                <div class="header-actions">
                    <button onclick="newProject()">New Project</button>
                    <button onclick="saveAll()">Save All</button>
                </div>
            </div>
            
            <!-- Content Area -->
            <div class="content-area">
                <!-- Chat Tab -->
                <div class="tab-content active" id="chat-tab">
                    <div class="chat-container">
                        <div class="messages" id="messages"></div>
                        <div class="chat-input">
                            <input type="text" id="chat-message" placeholder="Ask SubZero anything..." 
                                   onkeypress="if(event.key==='Enter') sendMessage()">
                            <button onclick="sendMessage()">Send</button>
                        </div>
                    </div>
                </div>
                
                <!-- Book Editor Tab -->
                <div class="tab-content" id="editor-tab">
                    <div class="editor-container">
                        <div class="chapters-list">
                            <h3>Chapters</h3>
                            <button class="btn btn-primary" style="width: 100%; margin: 10px 0;" onclick="newChapter()">
                                + New Chapter
                            </button>
                            <div id="chapters"></div>
                        </div>
                        <div class="editor">
                            <div class="editor-header">
                                <input type="text" id="chapter-title" placeholder="Chapter Title">
                                <button class="btn btn-primary" onclick="saveChapter()">Save</button>
                                <button class="btn btn-secondary" onclick="generateAudio()">🎙️ Audio</button>
                            </div>
                            <textarea class="editor-content" id="chapter-content" 
                                      placeholder="Write your book here..."></textarea>
                            <div style="margin-top: 10px; color: #666;">
                                Words: <span id="word-count">0</span> | Characters: <span id="char-count">0</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Audio Books Tab -->
                <div class="tab-content" id="audio-tab">
                    <div class="audiobook-container">
                        <div class="audio-controls">
                            <h3>Create Audio Book</h3>
                            <select id="voice-select">
                                <option>David - Male Voice</option>
                                <option>Zira - Female Voice</option>
                                <option>Mark - Male Voice</option>
                            </select>
                            <input type="range" min="0" max="100" value="100" id="volume">
                            <button class="btn btn-primary" onclick="generateFullAudioBook()">
                                Generate Full Audio Book
                            </button>
                        </div>
                        <h3>Generated Audio Files</h3>
                        <div class="audio-list" id="audio-list"></div>
                    </div>
                </div>
                
                <!-- Projects Tab -->
                <div class="tab-content" id="projects-tab">
                    <h2>My Projects</h2>
                    <div class="projects-grid" id="projects-grid"></div>
                </div>
                
                <!-- Settings Tab -->
                <div class="tab-content" id="settings-tab">
                    <h2>Settings</h2>
                    <div style="background: white; padding: 20px; border-radius: 10px;">
                        <h3>Ollama Model</h3>
                        <select id="model-select" style="width: 100%; padding: 10px; margin: 10px 0;">
                            <option>llama3.2</option>
                            <option>mistral</option>
                            <option>codellama</option>
                        </select>
                        
                        <h3 style="margin-top: 20px;">Auto-save</h3>
                        <input type="checkbox" id="autosave" checked> Enable auto-save
                        
                        <h3 style="margin-top: 20px;">Theme</h3>
                        <select style="width: 100%; padding: 10px;">
                            <option>Light</option>
                            <option>Dark</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <!-- Status Bar -->
            <div class="status-bar">
                <span>SubZero Studio v1.0</span>
                <span id="status">Ready</span>
            </div>
        </div>
    </div>
    
    <script>
        // Tab Switching
        function switchTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
        }
        
        // Chat Functions
        function sendMessage() {
            const input = document.getElementById('chat-message');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'user');
            input.value = '';
            
            // Call backend
            fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            })
            .then(r => r.json())
            .then(data => {
                addMessage(data.response, 'assistant');
            });
        }
        
        function addMessage(text, type) {
            const messages = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = 'message ' + type;
            msg.textContent = text;
            messages.appendChild(msg);
            messages.scrollTop = messages.scrollHeight;
        }
        
        // Editor Functions
        let currentChapter = null;
        
        function newChapter() {
            const title = prompt('Chapter title:');
            if (!title) return;
            
            const chapter = {
                id: Date.now(),
                title: title,
                content: ''
            };
            
            addChapterToList(chapter);
            loadChapter(chapter);
        }
        
        function addChapterToList(chapter) {
            const list = document.getElementById('chapters');
            const item = document.createElement('div');
            item.className = 'chapter-item';
            item.textContent = chapter.title;
            item.onclick = () => loadChapter(chapter);
            list.appendChild(item);
        }
        
        function loadChapter(chapter) {
            currentChapter = chapter;
            document.getElementById('chapter-title').value = chapter.title;
            document.getElementById('chapter-content').value = chapter.content || '';
            updateWordCount();
        }
        
        function saveChapter() {
            if (!currentChapter) return;
            
            currentChapter.title = document.getElementById('chapter-title').value;
            currentChapter.content = document.getElementById('chapter-content').value;
            
            fetch('/api/save-chapter', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(currentChapter)
            });
            
            setStatus('Chapter saved!');
        }
        
        function updateWordCount() {
            const content = document.getElementById('chapter-content').value;
            const words = content.trim().split(/\s+/).length;
            const chars = content.length;
            document.getElementById('word-count').textContent = words;
            document.getElementById('char-count').textContent = chars;
        }
        
        document.getElementById('chapter-content').addEventListener('input', updateWordCount);
        
        // Audio Functions
        function generateAudio() {
            if (!currentChapter) return;
            
            setStatus('Generating audio...');
            fetch('/api/generate-audio', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text: currentChapter.content,
                    title: currentChapter.title
                })
            })
            .then(r => r.json())
            .then(data => {
                setStatus('Audio generated!');
                loadAudioList();
            });
        }
        
        function generateFullAudioBook() {
            setStatus('Generating full audiobook...');
            // Implementation
        }
        
        function loadAudioList() {
            fetch('/api/audio-list')
            .then(r => r.json())
            .then(data => {
                const list = document.getElementById('audio-list');
                list.innerHTML = '';
                data.forEach(audio => {
                    const item = document.createElement('div');
                    item.className = 'audio-item';
                    item.innerHTML = '<h4>' + audio.title + '</h4><audio controls src="' + audio.url + '"></audio>';
                    list.appendChild(item);
                });
            });
        }
        
        // Projects Functions
        function loadProjects() {
            fetch('/api/projects')
            .then(r => r.json())
            .then(data => {
                const grid = document.getElementById('projects-grid');
                grid.innerHTML = '';
                data.forEach(project => {
                    const card = document.createElement('div');
                    card.className = 'project-card';
                    card.innerHTML = '<h3>' + project.name + '</h3><p>' + project.description + '</p>' +
                        '<div class="project-stats"><span>' + project.chapters + ' chapters</span>' +
                        '<span>' + project.words + ' words</span></div>';
                    grid.appendChild(card);
                });
            });
        }
        
        function newProject() {
            const name = prompt('Project name:');
            if (!name) return;
            // Create new project
        }
        
        function saveAll() {
            saveChapter();
            setStatus('All saved!');
        }
        
        function setStatus(text) {
            document.getElementById('status').textContent = text;
            setTimeout(() => {
                document.getElementById('status').textContent = 'Ready';
            }, 3000);
        }
        
        // Initialize
        loadProjects();
        loadAudioList();
    </script>
</body>
</html>
"@

# Save HTML
Set-Content "$StudioDir\index.html" $html

# Start Web Server
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      SubZero Studio - STARTED!          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`nStudio URL: http://localhost:$Port" -ForegroundColor Green
Write-Host "Opening browser..." -ForegroundColor Gray

Start-Sleep -Seconds 1
Start-Process "http://localhost:$Port"

Write-Host "`nPress Ctrl+C to stop server`n" -ForegroundColor Yellow

# Request Handler
while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response
    
    $url = $request.Url.LocalPath
    
    try {
        if ($url -eq "/" -or $url -eq "/index.html") {
            $response.ContentType = "text/html"
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($html)
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/chat") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $body = $reader.ReadToEnd() | ConvertFrom-Json
            
            # Call Ollama
            $aiResponse = ollama run llama3.2 $body.message
            
            $result = @{ response = $aiResponse } | ConvertTo-Json
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($result)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        elseif ($url -eq "/api/save-chapter") {
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $chapter = $reader.ReadToEnd() | ConvertFrom-Json
            
            $chapterFile = "$ProjectsDir\chapter_$($chapter.id).json"
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
            
            # Generate audio using Windows TTS
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
        elseif ($url -eq "/api/projects") {
            $projects = @(
                @{ name = "My First Book"; description = "A great story"; chapters = 5; words = 12500 }
            )
            $result = $projects | ConvertTo-Json
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
        else {
            $response.StatusCode = 404
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        Write-Host "Error: $errMsg" -ForegroundColor Red
        $response.StatusCode = 500
    }
    finally {
        $response.Close()
    }
}

$listener.Stop()
