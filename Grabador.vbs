' Lanzador de doble-clic para el Grabador de Reuniones.
' Abre la app SIN ventana de consola, usando el Python del entorno virtual.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
pyw  = root & "\.venv\Scripts\pythonw.exe"

sh.CurrentDirectory = root
If fso.FileExists(pyw) Then
    sh.Run """" & pyw & """ -m app.main", 0, False
Else
    MsgBox "No se encontró el entorno virtual (.venv)." & vbCrLf & _
           "Crea el entorno e instala dependencias primero:" & vbCrLf & _
           "  python -m venv .venv" & vbCrLf & _
           "  .\.venv\Scripts\Activate.ps1" & vbCrLf & _
           "  pip install -r requirements.txt", vbExclamation, "Grabador de Reuniones"
End If
