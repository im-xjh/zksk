@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SKILL_DIR=%SCRIPT_DIR%..\..\.cc-switch\skills\wechat-search-skill"

if not exist "%SKILL_DIR%" (
    echo Error: skill directory not found at %SKILL_DIR%
    exit /b 1
)

cd /d "%SKILL_DIR%" || (
    echo Error: failed to enter directory %SKILL_DIR%
    exit /b 1
)

"%SKILL_DIR%\.venv\Scripts\python.exe" sogou_search.py %*
endlocal
