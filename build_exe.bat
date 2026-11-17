@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo  Сборка автономного файла DesktopSnow.exe
echo ========================================================

python -m pyinstaller --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [1/2] Установка PyInstaller...
    pip install pyinstaller
)

echo [2/2] Компиляция приложения в один .exe файл...
python -m pyinstaller --noconsole --onefile --icon="snowflake.ico" --name="DesktopSnow" main.py

if exist "dist\DesktopSnow.exe" (
    echo.
    echo ========================================================
    echo  [OK] Готово! Исполняемый файл создан:
    echo  dist\DesktopSnow.exe
    echo.
    echo  Его можно выложить в GitHub Releases или отправить друзьям:
    echo  он запускается на любом Windows ПК без установки Python!
    echo ========================================================
) else (
    echo.
    echo [!] Ошибка во время сборки.
)
pause
