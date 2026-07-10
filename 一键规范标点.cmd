@echo off
setlocal

set "SCRIPT=%~dp0normalize_punctuation.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*

echo.
pause
