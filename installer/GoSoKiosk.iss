; Inno Setup — GoSo Kiosk (bộ cài dùng chung cho mọi Chi nhánh)
; Build:  iscc /DMyAppVersion=1.0.7 installer\GoSoKiosk.iss
; Output: dist\GoSoKiosk_Setup_<version>.exe

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "GoSo Kiosk"
#define MyAppPublisher "Van phong Dang ky Dat dai"
#define AppDir "GoSo Kiosk"
#define DataDir "{commonappdata}\GoSoKiosk"

[Setup]
AppId={{7C4E1B2A-9F3D-4A55-9E21-GOSO-KIOSK}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#AppDir}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=GoSoKiosk_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName={#MyAppName} {#MyAppVersion}
SetupLogging=yes

[Languages]
Name: "vi"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo shortcut ngoài Desktop"; Flags: unchecked

[Files]
; toàn bộ nội dung dist\GoSoKiosk\ -> Program Files\GoSo Kiosk\
Source: "..\dist\GoSoKiosk\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Dirs]
; dữ liệu máy — KHÔNG bị gỡ khi uninstall, KHÔNG bị update ghi đè
Name: "{#DataDir}"; Permissions: users-modify
Name: "{#DataDir}\logs"; Permissions: users-modify
Name: "{#DataDir}\updates"; Permissions: users-modify
Name: "{#DataDir}\backup"; Permissions: users-modify
Name: "{#DataDir}\state"; Permissions: users-modify

[Icons]
Name: "{group}\GoSo Kiosk"; Filename: "{app}\GoSoKiosk.exe"
Name: "{group}\GoSo Kiosk - Cấu hình"; Filename: "{app}\GoSoConfig.exe"
Name: "{group}\Gỡ cài đặt GoSo Kiosk"; Filename: "{uninstallexe}"
Name: "{autodesktop}\GoSo Kiosk"; Filename: "{app}\GoSoKiosk.exe"; Tasks: desktopicon

[Run]
; Sau lần cài MỚI (chưa có config) -> mở Configurator. Upgrade thì bỏ qua.
Filename: "{app}\GoSoConfig.exe"; Description: "Cấu hình kiosk cho máy này"; \
  Flags: postinstall nowait skipifsilent; Check: not ConfigExists

[UninstallDelete]
; chỉ xoá binaries; giữ nguyên {#DataDir} (config/device/logs) — người dùng tự xoá nếu muốn

[Code]
function ConfigExists: Boolean;
begin
  Result := FileExists(ExpandConstant('{#DataDir}\config.json'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(ExpandConstant('{#DataDir}'));
  end;
end;
