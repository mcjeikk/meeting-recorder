# Pruebas de las dos partes del repositorio, cada una con SU entorno.
#
#   .\run_all_tests.ps1
#
# La app (raiz) y el motor (transcriptor\) tienen .venv distintos a proposito:
# el motor trae torch/pyannote y la app no debe depender de ellos. Por eso no
# hay un solo "python -m unittest" para todo. Si el motor no esta instalado, su
# suite se omite (la app se puede usar solo para grabar) y se dice.
#
# Solo ASCII en este archivo: PowerShell 5.1 lee los .ps1 sin BOM como ANSI.

$raiz = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:QT_QPA_PLATFORM = "offscreen"   # construir ventanas sin mostrarlas
$fallos = 0

function Invoke-Suite($nombre, $carpeta, $argumentos) {
    $py = Join-Path $carpeta ".venv\Scripts\python.exe"
    Write-Host "`n=== $nombre ===" -ForegroundColor Cyan
    if (-not (Test-Path $py)) {
        Write-Host "  omitida: falta $py" -ForegroundColor Yellow
        return $null
    }
    Push-Location $carpeta
    try {
        # unittest escribe en stderr; se junta todo y se muestra solo el veredicto.
        $salida = & $py -m unittest @argumentos 2>&1 | ForEach-Object { "$_" }
        $codigo = $LASTEXITCODE
        $salida | Where-Object { $_ -match "^(Ran |OK|FAILED|FAIL:|ERROR:)" } |
            ForEach-Object { Write-Host "  $_" }
        return $codigo
    } finally {
        Pop-Location
    }
}

$app = Invoke-Suite "App (grabacion e integracion)" $raiz @("discover", "-s", "tests", "-t", ".")
if ($null -eq $app -or $app -ne 0) { $fallos++ }

$motor = Invoke-Suite "Motor de transcripcion (transcriptor\)" (Join-Path $raiz "transcriptor") @("discover", "-s", "tests")
if ($null -ne $motor -and $motor -ne 0) { $fallos++ }

Write-Host ""
if ($fallos -eq 0) {
    Write-Host "Todo en verde." -ForegroundColor Green
} else {
    Write-Host "Hay fallos en $fallos suite(s)." -ForegroundColor Red
}
exit $fallos
