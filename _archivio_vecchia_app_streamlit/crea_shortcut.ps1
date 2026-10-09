# Script PowerShell per creare l'icona ufficiale di Futures Cereali sul Desktop
$ws = New-Object -ComObject WScript.Shell
$desk = [System.Environment]::GetFolderPath('Desktop')
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$batPath = Join-Path $baseDir 'avvia_app.bat'
$icoPath = Join-Path $baseDir 'favicon.ico'
if (-not (Test-Path $icoPath)) {
    $icoPath = Join-Path (Join-Path $baseDir 'static') 'favicon.ico'
}

$lnkPath = Join-Path $desk 'Futures Cereali.lnk'
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $batPath
$lnk.WorkingDirectory = $baseDir
$lnk.IconLocation = "$icoPath,0"
$lnk.Description = "Quotazioni Futures Cereali - Grano Duro e Grano Tenero"
$lnk.Save()

Write-Host "Collegamento creato con successo in: $lnkPath"
