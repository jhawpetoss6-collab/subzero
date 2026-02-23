$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("C:\Users\jhawp\Desktop\Spine Rip.lnk")
$s.TargetPath = "C:\Python314\pythonw.exe"
$s.Arguments = "C:\Users\jhawp\subzero\warp_oz.pyw"
$s.WorkingDirectory = "C:\Users\jhawp\subzero"
$s.IconLocation = "C:\Users\jhawp\subzero\spinerip.ico,0"
$s.Description = "Spine Rip - Sub-Zero AI Terminal"
$s.Save()
Write-Output "Spine Rip shortcut created on desktop."
