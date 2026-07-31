@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SPIDER_DIR=%SCRIPT_DIR%my_weibospider\weibospider"

if not exist "%SPIDER_DIR%" (
    echo Error: spider directory not found at %SPIDER_DIR%
    exit /b 1
)

cd /d "%SPIDER_DIR%" || (
    echo Error: failed to enter directory %SPIDER_DIR%
    exit /b 1
)

"..\.venv\Scripts\python.exe" run_spider.py %*
endlocal
