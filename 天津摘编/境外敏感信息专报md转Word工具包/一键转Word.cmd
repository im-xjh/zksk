@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=C:\Users\直报点\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%PYTHON_EXE%" goto :run
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=py -3"
    goto :run
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
    goto :run
)

echo 未找到 Python。请先安装 Python 3，或使用 Claude/Codex 内置 Python 运行。
pause
exit /b 1

:run
"%PYTHON_EXE%" -m pip show python-docx >nul 2>nul
if not %errorlevel%==0 (
    echo 正在安装依赖...
    "%PYTHON_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    if not %errorlevel%==0 (
        echo 依赖安装失败。
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" "%SCRIPT_DIR%convert.py" --interactive %*
if not %errorlevel%==0 (
    echo.
    echo 转换失败，请查看上方错误信息。
    pause
    exit /b 1
)
endlocal
