; ============================================================
;  StreamBridge — Inno Setup Installer Script
;  Creates a professional Windows installer with:
;   - FFmpeg bundled
;   - Start Menu & Desktop shortcuts
;   - Uninstaller with config cleanup
;   - Auto-start option
; ============================================================

#define MyAppName "StreamBridge"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "StreamBridge"
#define MyAppURL "https://github.com/eitan-ui/StreamBridge"
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
PrivilegesRequired=admin
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start StreamBridge with Windows"; GroupDescription: "Other:"

[Files]
; Main application — onedir build (exe + all Python DLLs + dependencies)
Source: "..\dist\StreamBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; FFmpeg (bundled)
Source: "..\dist\ffmpeg\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\ffmpeg\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Icon for shortcuts (separate copy so it's accessible even if _internal moves)
Source: "..\resources\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; User documentation
Source: "..\README_USER.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion isreadme skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; Auto-start with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "StreamBridge"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Launch after interactive install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
; Auto-launch after silent install (auto-update path)
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser skipifnotsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"

[Code]
function InitializeSetup: Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Always kill any running instance and its ffmpeg subprocess
  Exec('taskkill', '/f /im StreamBridge.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im ffmpeg.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1500);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ConfigDir := ExpandConstant('{userappdata}\StreamBridge');
    if DirExists(ConfigDir) then
    begin
      if MsgBox('Remove StreamBridge settings and configuration data?',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(ConfigDir, True, True, True);
      end;
    end;
  end;
end;
