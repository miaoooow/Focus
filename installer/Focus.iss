#ifndef MyAppVersion
  #define MyAppVersion "4.0.0"
#endif

#define MyAppName "Focus"
#define MyAppExeName "Focus.exe"

[Setup]
AppId={{94AE7CFB-5820-4FA5-BC0F-5EA5B087F355}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Focus
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Focus
DefaultGroupName={#MyAppName}
DisableWelcomePage=yes
DisableDirPage=no
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=Focus-Windows-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\branding\focus.ico
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\Focus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait skipifsilent
