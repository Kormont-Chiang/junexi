#define MyAppName "六月息"
#define MyAppVersion "0.1.6"
#define MyAppPublisher "JuneXi Project"
#define MyAppExeName "JuneXi.exe"

[Setup]
AppId={{B7A1C4E2-6F3D-4A8B-9C5E-2D7F1A3B6E9D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=历史学学术工作台：CBDB 史料检索 · 地理可视化 · AI 辅助
DefaultDirName={localappdata}\Programs\JuneXi
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=JuneXi-Setup-0.1.6
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: checkedonce

[Files]
Source: "C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\dist\JuneXi\JuneXi.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\dist\JuneXi\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: postinstall skipifsilent

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
  Key: String;
begin
  { 官方检测口径：64 位 Windows 上 pv 值须非空且非 0.0.0.0 }
  Result := False;
  Key := 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  if RegQueryStringValue(HKLM, Key, 'pv', Version) then
    Result := (Version <> '') and (Version <> '0.0.0.0');
  if not Result then
  begin
    Key := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
    if RegQueryStringValue(HKCU, Key, 'pv', Version) then
      Result := (Version <> '') and (Version <> '0.0.0.0');
  end;
end;

function AccessDriverInstalled: Boolean;
var
  DriverName: String;
begin
  DriverName := 'Microsoft Access Driver (*.mdb, *.accdb)';
  Result :=
    RegValueExists(HKLM, 'SOFTWARE\ODBC\ODBCINST.INI\ODBC Drivers', DriverName) or
    RegValueExists(HKLM, 'SOFTWARE\WOW6432Node\ODBC\ODBCINST.INI\ODBC Drivers', DriverName) or
    RegKeyExists(HKLM, 'SOFTWARE\ODBC\ODBCINST.INI\Microsoft Access Driver (*.mdb, *.accdb)');
end;

function InitializeSetup: Boolean;
var
  Missing, Msg: String;
begin
  Result := True;
  Missing := '';
  if not WebView2Installed then
    Missing := Missing + #13#10 + '  - WebView2 运行时（程序窗口引擎）';
  if not AccessDriverInstalled then
    Missing := Missing + #13#10 + '  - Microsoft Access 数据库引擎（CBDB 人物库检索用）';
  if Missing <> '' then
  begin
    Msg := '安装前体检：本机缺少以下运行组件' + #13#10 + Missing + #13#10 + #13#10 +
           '缺少它们会导致：窗口无法打开 / 人物数据库检索不可用。' + #13#10 + #13#10 +
           '建议先取消，装好组件后重新运行本安装包：' + #13#10 +
           '  WebView2 运行时的官方安装链接：' + #13#10 +
           '    https://go.microsoft.com/fwlink/?LinkId=2124703' + #13#10 +
           '  Access 引擎：在 microsoft.com 搜索' + #13#10 +
           '    "Access Database Engine 2016 可再发行程序包"（选 64 位版）' + #13#10 + #13#10 +
           '仍然继续安装吗？';
    Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
  end;
end;
