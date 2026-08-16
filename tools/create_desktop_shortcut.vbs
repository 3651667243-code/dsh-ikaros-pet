' create_desktop_shortcut.vbs
' Creates a desktop shortcut "Ikaros Pet" for this project.
' Usage (double-click or from command line):
'   wscript create_desktop_shortcut.vbs [path-to-launcher]
' The launcher defaults to <repo>\start.bat. If your launcher lives
' elsewhere (e.g. D:\sakura\ikaros_pet.vbs), pass its full path as the
' first argument. The icon comes from <repo>\assets\ikaros_pet.ico.
Option Explicit
Dim ws, fso, repoDir, launcher, iconPath, lnkPath, shortcut
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' repo root = parent of this script's folder (script lives in tools/)
repoDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
iconPath = repoDir & "\assets\ikaros_pet.ico"

If WScript.Arguments.Count > 0 Then
    launcher = WScript.Arguments(0)
Else
    launcher = repoDir & "\start.bat"
End If

If Not fso.FileExists(launcher) Then
    WScript.Echo "Launcher not found: " & launcher
    WScript.Quit 1
End If
If Not fso.FileExists(iconPath) Then
    iconPath = ""
End If

lnkPath = ws.SpecialFolders("Desktop") & "\伊卡洛斯桌宠.lnk"
Set shortcut = ws.CreateShortcut(lnkPath)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & launcher & """"
shortcut.WorkingDirectory = fso.GetParentFolderName(launcher)
shortcut.Description = "Ikaros desktop pet (DSH-aware)"
If iconPath <> "" Then shortcut.IconLocation = iconPath
shortcut.Save()

WScript.Echo "Shortcut created: " & lnkPath
