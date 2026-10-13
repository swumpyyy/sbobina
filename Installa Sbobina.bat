@echo off
rem Doppio clic: installa Sbobina e mette il collegamento sul Desktop (serve una volta sola).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\installa_windows.ps1"
pause
