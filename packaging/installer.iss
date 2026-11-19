; Instalador de GestIA para Windows 10/11 de 64 bits (P3-24 y P3-25), con Inno Setup 6.
; Uso: iscc /DAppVersion=0.7.0 packaging\installer.iss  (después de PyInstaller)
; Resultado: dist\GestIA-Setup.exe
;
; - Se instala para el usuario actual, sin pedir permisos de administrador.
; - Incluye el modelo: tras instalar funciona sin internet.
; - La tarea «Iniciar GestIA al encender el equipo» escribe la misma clave que el interruptor
;   «Iniciar con Windows» de la app (HKCU\...\Run, valor «GestIA»).
; - Desinstalar borra el programa y el inicio automático, pero conserva los perfiles en
;   %LOCALAPPDATA%\GestIA (calibración y ajustes de cada persona).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7E3B9B52-6C1D-4F4A-9F2E-4C5A1E0B6D21}
AppName=GestIA
AppVersion={#AppVersion}
AppVerName=GestIA {#AppVersion}
AppPublisher=Equipo GestIA
AppPublisherURL=https://github.com/Claudia02102/GestIA
DefaultDirName={localappdata}\Programs\GestIA
DefaultGroupName=GestIA
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=GestIA-Setup
SetupIconFile=gestia.ico
UninstallDisplayIcon={app}\GestIA.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar GestIA al encender el equipo (recomendado)"; GroupDescription: "Inicio:"
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\GestIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\GestIA"; Filename: "{app}\GestIA.exe"
Name: "{autodesktop}\GestIA"; Filename: "{app}\GestIA.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GestIA"; ValueData: """{app}\GestIA.exe"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\GestIA.exe"; Description: "Abrir GestIA ahora"; Flags: nowait postinstall skipifsilent

[Code]
{ Si la persona activó «Iniciar con Windows» desde la app, también se quita al desinstalar. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'GestIA');
end;
