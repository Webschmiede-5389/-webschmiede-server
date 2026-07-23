' Startet Requesty Cursor-Router unsichtbar beim Windows-Login
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
' Script liegt in Server\scripts → Root = Server
cmd = "python -u """ & root & "\scripts\requesty_cursor_router.py"""
sh.CurrentDirectory = root
sh.Run cmd, 0, False
