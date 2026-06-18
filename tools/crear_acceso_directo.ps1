# Crea (o recrea) el acceso directo "Grabador de Reuniones" en el Escritorio.
# Útil si mueves la carpeta del proyecto y el acceso directo deja de funcionar.
$root = Split-Path -Parent $PSScriptRoot
$pyw  = Join-Path $root ".venv\Scripts\pythonw.exe"
$icon = Join-Path $root "assets\icon.ico"

if (-not (Test-Path $pyw)) {
    Write-Host "No se encontró $pyw" -ForegroundColor Red
    Write-Host "Crea el entorno primero: python -m venv .venv ; pip install -r requirements.txt"
    return
}

$ws  = New-Object -ComObject WScript.Shell
$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Grabador de Reuniones.lnk"
$s = $ws.CreateShortcut($lnk)
$s.TargetPath       = $pyw
$s.Arguments        = "-m app.main"
$s.WorkingDirectory = $root
$s.IconLocation     = "$icon,0"
$s.Description       = "Grabador de Reuniones"
$s.WindowStyle      = 1
$s.Save()
Write-Host "Acceso directo creado en el Escritorio." -ForegroundColor Green
