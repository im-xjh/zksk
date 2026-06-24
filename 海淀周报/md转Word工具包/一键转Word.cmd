@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "TOOL=%SCRIPT_DIR%convert.py"
set "REQ=%SCRIPT_DIR%requirements.txt"
set "PY_EXE="
set "PY_ARGS="

set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PY%" (
    set "PY_EXE=%BUNDLED_PY%"
    goto python_found
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_EXE=py"
    set "PY_ARGS=-3"
    goto python_found
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_EXE=python"
    goto python_found
)

echo 未找到 Python 3。请先安装 Python，再重新运行本工具。
pause
exit /b 1

:python_found
"%PY_EXE%" %PY_ARGS% -c "import docx, PIL" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 正在安装首次运行所需依赖，请稍候...
    "%PY_EXE%" %PY_ARGS% -m pip install --disable-pip-version-check -r "%REQ%"
    if %ERRORLEVEL% NEQ 0 (
        echo 依赖安装失败，请检查网络或 Python 环境。
        pause
        exit /b 1
    )
)

"%PY_EXE%" %PY_ARGS% "%TOOL%" --interactive %*
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% NEQ 0 (
    echo.
    echo 转换未完成，请根据提示修正后重试。
    pause
)
exit /b %EXIT_CODE%
