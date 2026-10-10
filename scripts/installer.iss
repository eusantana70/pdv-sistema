; Inno Setup — instalador único do PDV-Sorvetes para Windows.
; Requer: Inno Setup 6 instalado (só na máquina de build).
; Uso: abrir este .iss no Inno Setup > Compile. Saída: installer\PDV-Sorvetes-Setup.exe
; O app é portable: banco fica em %LOCALAPPDATA%\pdv-sistema\pdv.db na primeira execução.

#define MyAppName "PDV Sorvetes"
#define MyAppVersion "0.1.0"
#define MyAppExe "PDV-Sorvetes.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PDV Sorvetes
OutputDir=installer
OutputBaseFilename=PDV-Sorvetes-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Executar o PDV agora"; Flags: nowait postinstall skipifsilent
