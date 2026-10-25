; Inno Setup script — builds Converz-Setup-x.y.z.exe from dist\Converz
; Installs for the current user only (no admin password needed).

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{8C2B6E52-6B1F-4C1E-9E1A-3F7B2D9C4A11}
AppName=Converz
AppVersion={#MyAppVersion}
AppPublisher=Converz
DefaultDirName={localappdata}\Programs\Converz
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Converz-Setup-{#MyAppVersion}
SetupIconFile=..\assets\converz.ico
UninstallDisplayIcon={app}\Converz.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Converz\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Converz"; Filename: "{app}\Converz.exe"
Name: "{userdesktop}\Converz"; Filename: "{app}\Converz.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Converz.exe"; Description: "Open Converz now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Converz.exe"; Flags: runhidden; RunOnceId: "StopConverz"

[Registry]
; The app adds itself to "start with Windows"; remove that on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Converz"; Flags: uninsdeletevalue

[UninstallDelete]
Type: files; Name: "{userappdata}\Microsoft\Windows\SendTo\Converz*.lnk"
