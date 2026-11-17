@echo off
set SCRIPT_DIR=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\Desktop\❄️ Новогодний Снег.lnk

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = 'wscript.exe'; $Shortcut.Arguments = '\"%SCRIPT_DIR%start_silent.vbs\"'; $Shortcut.WorkingDirectory = '%SCRIPT_DIR%'; $Shortcut.IconLocation = '%SCRIPT_DIR%snowflake.ico, 0'; $Shortcut.Description = 'Новогодний снег на окнах'; $Shortcut.Save()"

echo Shortcut created on Desktop: %SHORTCUT_PATH%
pause
