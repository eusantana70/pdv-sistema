; Instalador do PDV Lumina (Inno Setup 6).
;
; Decisões pensadas para não dar erro na hora de instalar:
;  - PrivilegesRequired=lowest: instala em %LOCALAPPDATA%\Programs, sem
;    pedir senha de administrador e sem o UAC atrapalhando;
;  - o banco NÃO fica na pasta do programa: o PDV grava em
;    %LOCALAPPDATA%\PDV Lumina. Então atualizar ou desinstalar o programa
;    nunca apaga vendas, produtos e usuários.
;
; Gerar:  ISCC.exe PDV-Lumina.iss

#define Versao "2.1.0"
#define NomeApp "PDV Lumina"
#define NomeFab "PDV Lumina"
#define PastaFonte "..\dist\PDV Lumina"
#define PastaSaida "..\installer"

[Setup]
AppId={{7C4E9B21-6F3A-4C58-9D0E-2A5B7C1E4D33}
AppName={#NomeApp}
AppVersion={#Versao}
AppVerName={#NomeApp} {#Versao}
DefaultDirName={localappdata}\Programs\{#NomeApp}
DefaultGroupName={#NomeApp}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#PastaSaida}
OutputBaseFilename=PDV-Lumina-Setup-{#Versao}
SetupIconFile=..\build_assets\pdv_lumina.ico
UninstallDisplayIcon={app}\PDV Lumina.exe
UninstallDisplayName={#NomeApp} {#Versao}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
; arquivo grande: não deixa o antivírus travar o instalador em 50% e acordar
; o usuário achando que quebrou
CloseApplications=yes
CloseApplicationsFilter=*.exe|*.dll|*.pyd
RestartApplications=no
DisableDirPage=no
InfoBeforeFile=..\build_assets\LEIAME.txt

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; o programa inteiro vem do build do PyInstaller
Source: "{#PastaFonte}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; pasta de dados — criada pelo próprio PDV no 1º uso, aqui só garantimos que
; exista (o .exe também recria se faltar)
Name: "{localappdata}\{#NomeApp}"

[Icons]
; o grupo do menu Iniciar é sempre criado (DisableProgramGroupPage=yes)
Name: "{group}\{#NomeApp}"; Filename: "{app}\PDV Lumina.exe"; WorkingDir: "{app}"; IconFilename: "{app}\PDV Lumina.exe"
Name: "{group}\Desinstalar {#NomeApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#NomeApp}"; Filename: "{app}\PDV Lumina.exe"; WorkingDir: "{app}"; IconFilename: "{app}\PDV Lumina.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PDV Lumina.exe"; Description: "Abrir o {#NomeApp}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallDelete]
; só o cache do navegador que o próprio PDV cria dentro da pasta dele
Type: filesandordirs; Name: "{app}\navegador"

[Code]
{ Na desinstalacao os dados do usuario sao preservados de proposito:
  %LOCALAPPDATA%\PDV Lumina guardaria vendas, produtos e usuarios. Para
  recomecar do zero, apague essa pasta (ou rode scripts\limpar_instalacao.py). }
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PastaDados: String;
begin
  if CurStep = ssPostInstall then
  begin
    PastaDados := ExpandConstant('{localappdata}\{#NomeApp}');
    if not DirExists(PastaDados) then
      CreateDir(PastaDados);
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;