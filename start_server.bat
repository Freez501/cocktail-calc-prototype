@echo off
chcp 65001 >nul
cd /d "%~dp0"

py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :run
)

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :run
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python3
    goto :run
)

echo Python не найден. Установите Python или запустите сервер вручную:
echo uvicorn web.main:app --reload
pause
exit /b 1

:run
:: Завершаем старый сервер на порту 8000, если он остался висеть
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000"') do (
    echo Stopping old server process %%p...
    taskkill /PID %%p /F 2>nul
)
timeout /t 1 /nobreak >nul

echo =========================================
echo   CocktailCalc Pro server starting
echo =========================================
echo.
echo Admin: http://127.0.0.1:8000/admin
echo Login: admin
echo Password: admin
echo.
echo Stop: Ctrl + C in this window
echo.
start http://127.0.0.1:8000/admin
%PYTHON_CMD% -m uvicorn web.main:app --reload --host 127.0.0.1 --port 8000
if errorlevel 1 (
    echo.
    echo Ошибка запуска сервера.
    pause
)
