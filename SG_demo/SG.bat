@echo off
rem Usage: double-click SG.bat, or run SG.bat in a terminal from any folder.
rem Optional: SG.bat -Port 8766 -Python "C:\path\to\python.exe"
rem Keep this window open. Press Ctrl+C to stop the service.
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0SG.ps1" %*
if errorlevel 1 pause
