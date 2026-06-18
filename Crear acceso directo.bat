@echo off
REM Crea un acceso directo del Grabador en tu Escritorio (doble clic para abrir la app).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\crear_acceso_directo.ps1"
echo.
pause
