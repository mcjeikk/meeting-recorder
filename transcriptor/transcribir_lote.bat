@echo off
REM ============================================================
REM  Transcriptor - procesamiento por lotes / nocturno
REM  - Doble clic: procesa TODOS los audios de la carpeta input\
REM  - O:  transcribir_lote.bat "C:\ruta\reunion.m4a"  [opciones]
REM  El progreso se guarda en output\log_<fecha>.txt para que
REM  puedas dejarlo corriendo y revisar despues.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
if not exist "output" mkdir "output"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
set "LOG=output\log_%TS%.txt"

echo Procesamiento iniciado. El progreso se guarda en: %LOG%
echo Puedes minimizar esta ventana y volver mas tarde.
echo.

if "%~1"=="" (
  python transcribe.py "input" --batch > "%LOG%" 2>&1
) else (
  python transcribe.py %* > "%LOG%" 2>&1
)

echo.
echo === FINALIZADO ===  Resultados en la carpeta  output\
echo Log completo: %LOG%
pause
