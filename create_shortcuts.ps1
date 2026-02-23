$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')

# 1. Custom Terminal shortcut
$Shortcut = $WshShell.CreateShortcut("$Desktop\Custom Terminal.lnk")
$Shortcut.TargetPath = "C:\Python314\pythonw.exe"
$Shortcut.Arguments = "`"C:\Users\jhawp\subzero\custom_terminal.py`""
$Shortcut.WorkingDirectory = "C:\Users\jhawp\subzero"
$Shortcut.Description = "Custom Terminal - Command execution with AI integration"
$Shortcut.IconLocation = "C:\Windows\System32\cmd.exe,0"
$Shortcut.Save()
Write-Host "Created: Custom Terminal.lnk"

# 2. TM Widget shortcut
$Shortcut = $WshShell.CreateShortcut("$Desktop\TM Widget.lnk")
$Shortcut.TargetPath = "C:\Python314\pythonw.exe"
$Shortcut.Arguments = "`"C:\Users\jhawp\subzero\terminal_widget.py`""
$Shortcut.WorkingDirectory = "C:\Users\jhawp\subzero"
$Shortcut.Description = "Terminal Manager Widget - Tasks, Files, Notifications"
$Shortcut.IconLocation = "C:\Windows\System32\taskmgr.exe,0"
$Shortcut.Save()
Write-Host "Created: TM Widget.lnk"

# 3. Launch Both shortcut
$Shortcut = $WshShell.CreateShortcut("$Desktop\SubZero Suite.lnk")
$Shortcut.TargetPath = "C:\Python314\pythonw.exe"
$Shortcut.Arguments = "`"C:\Users\jhawp\subzero\launch_all.pyw`""
$Shortcut.WorkingDirectory = "C:\Users\jhawp\subzero"
$Shortcut.Description = "Launch Custom Terminal + TM Widget together"
$Shortcut.IconLocation = "C:\Windows\System32\shell32.dll,176"
$Shortcut.Save()
Write-Host "Created: SubZero Suite.lnk"

Write-Host ""
Write-Host "All 3 desktop shortcuts created!"
