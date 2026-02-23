# IronLung 3 - Desktop Shortcut Creator
# Run this once: right-click > "Run with PowerShell"

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$batFile    = Join-Path $projectDir "ironlung3.bat"
$iconFile   = Join-Path $projectDir "ironlung3.ico"
$desktop    = [Environment]::GetFolderPath("Desktop")
$shortcut   = Join-Path $desktop "IronLung 3.lnk"

# Create the shortcut
$shell = New-Object -ComObject WScript.Shell
$lnk   = $shell.CreateShortcut($shortcut)
$lnk.TargetPath       = $batFile
$lnk.WorkingDirectory  = $projectDir
$lnk.Description       = "IronLung 3 - Sales Pipeline Manager"
$lnk.WindowStyle       = 1  # Normal window

# Use custom icon if present, otherwise use Python's icon
if (Test-Path $iconFile) {
    $lnk.IconLocation = $iconFile
} else {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($pythonExe) {
        $lnk.IconLocation = "$pythonExe,0"
    }
}

$lnk.Save()
Write-Host ""
Write-Host "  Desktop shortcut created: $shortcut" -ForegroundColor Green
Write-Host "  Double-click 'IronLung 3' on your desktop to launch." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
