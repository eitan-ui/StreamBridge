; ============================================================
;  StreamBridge — Inno Setup Installer Script
;  Creates a professional Windows installer with:
;   - FFmpeg bundled
;   - Start Menu & Desktop shortcuts
;   - Uninstaller
;   - Auto-start option
; ============================================================

#define MyAppName "StreamBridge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "StreamBridge"
#define MyAppURL "https://github.com/yourusername/streambridge"
#define MyAppExeName "StreamBridge.exe"

[Setup]
AppId={{B8F3E2A1-7C4D-4E9F-A1B2-3C4D5E6F7890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=StreamBridge-{#MyAppVersion}-Setup
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start StreamBridge with Windows"; GroupDescription: "Other:"

[Files]
; Main application
Source: "..\dist\StreamBridge.exe"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg (bundled)
Source: "..\dist\ffmpeg\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\ffmpeg\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Resources
Source: "..\resources\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\resources\icon.png"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "..\resources\fonts\*"; DestDir: "{app}\resources\fonts"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; Auto-start with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "StreamBridge"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"

[Code]
function InitializeSetup: Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Check for running instance
  if CheckForMutexes('StreamBridgeMutex') then
  begin
    if MsgBox('StreamBridge is currently running. Close it before installing?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill', '/f /im StreamBridge.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);
    end
    else
      Result := False;
  end;
end;
