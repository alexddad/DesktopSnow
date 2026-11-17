@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ========================================================
    echo  [!] Ошибка: Python не обнаружен в системе.
    echo  Установите Python 3 с официального сайта:
    echo  https://www.python.org/downloads/
    echo.
    echo  ВАЖНО: При установке отметьте галочку:
    echo  "Add python.exe to PATH"
    echo ========================================================
    pause
    exit /b 1
)

python -c "import PyQt6" >nul 2>nul
if %errorlevel% neq 0 (
    echo ========================================================
    echo  Первый запуск: установка зависимостей (PyQt6)...
    echo ========================================================
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [!] Не удалось автоматически установить библиотеки.
        pause
        exit /b 1
    )
)

echo Запуск приложения Desktop Snow...
start "" pythonw "%~dp0main.py"
