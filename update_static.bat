@echo off
chcp 65001 >nul
python update_static.py
if errorlevel 1 (
    echo.
    echo Не удалось запустить python. Попробуйте python3 update_static.py или py update_static.py
    pause
) else (
    pause
)
