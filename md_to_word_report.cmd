@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "TOOL=%SCRIPT_DIR%md_to_word_report.py"
set "PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%PY%" goto run_tool

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY=python"
    goto run_tool
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY=py"
    goto run_tool
)

echo Python was not found. Install Python or run this from Codex.
exit /b 1

:run_tool
"%PY%" "%TOOL%" %*
exit /b %ERRORLEVEL%
