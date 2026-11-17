Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = appDir
WshShell.Run "pythonw """ & appDir & "\main.py""", 0, False
