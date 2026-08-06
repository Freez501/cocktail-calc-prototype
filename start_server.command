#!/bin/bash
# Запуск CocktailCalc Pro на macOS (аналог start_server.bat для Windows)

cd "$(dirname "$0")"

echo "========================================="
echo "  CocktailCalc Pro server starting"
echo "========================================="
echo ""
echo "Admin: http://127.0.0.1:8000/admin"
echo "Login: admin"
echo "Password: admin"
echo ""
echo "Stop: Ctrl + C in this window"
echo ""

# Завершаем старый сервер на порту 8000, если он остался висеть
OLD_PID=$(lsof -ti :8000)
if [ -n "$OLD_PID" ]; then
    echo "Stopping old server process $OLD_PID..."
    kill $OLD_PID 2>/dev/null
    sleep 1
fi

open "http://127.0.0.1:8000/admin"

# Используем Python из виртуального окружения проекта, иначе системный
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" -m uvicorn web.main:app --reload --host 127.0.0.1 --port 8000

echo ""
echo "Ошибка запуска сервера. Нажмите любую клавишу..."
read -n 1
