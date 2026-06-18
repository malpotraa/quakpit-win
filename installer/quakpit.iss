; Inno Setup script for Quakpit (Windows).
; Compile with:  ISCC.exe installer\quakpit.iss   (or run ..\build.py)
; Produces:      ..\dist\installer\Quakpit-Setup.exe

#define MyAppName "Quakpit"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Ooble Studio"
#define MyAppURL "https://ooble.studio"
#define MyAppExeName "Quakpit.exe"

[Setup]
AppId={{B7D2A1C4-9E3F-4A21-9B6E-7C1A2D3E4F50}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user install — no admin rights needed, and autostart works cleanly.
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=Quakpit-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\quakpit\assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startupicon"; Description: "Start {#MyAppName} automatically when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; The whole PyInstaller one-folder build.
Source: "..\dist\Quakpit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Autostart via the per-user Startup folder when the task is checked.
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"
