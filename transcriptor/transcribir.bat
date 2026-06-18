@echo off
REM ============================================================
REM  Transcriptor de Reuniones - atajo para Windows
REM  Uso:  transcribir.bat "ruta\al\audio.m4a"  [opciones]
REM  Tambien puedes ARRASTRAR un archivo de audio sobre este .bat
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

python transcribe.py %*

echo.
pause
