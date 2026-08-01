@echo off
setlocal
set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=start"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Homer-Offline.ps1" -Action "%ACTION%"
exit /b %ERRORLEVEL%
