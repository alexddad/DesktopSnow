@echo off
echo Stopping Desktop Snow...
powershell -NoProfile -Command "$p = '%~dp0main.py'; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like ('*' + $p + '*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Done!
