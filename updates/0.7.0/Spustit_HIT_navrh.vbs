Option Explicit
Dim shell, fso, folder, script, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
script = folder & "\hit_designer.pyw"
cmd = "pyw """ & script & """"
shell.Run cmd, 0, False
