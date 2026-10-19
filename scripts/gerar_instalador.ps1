<#
.SYNOPSIS
  Gera o instalador do PDV Lumina do zero: icone -> tela -> .exe -> instalador.

.DESCRIPTION
  Cada etapa para se falhar. O .exe passa por um autoteste antes de virar
  instalador — se faltar biblioteca ou recurso, o build para aqui em vez de
  o cliente descobrir na hora de abrir.

.PARAMETER Saida
  Pasta onde o instalador .exe será copiado ao final.
  Padrão: a pasta "PDV Lumina" na Área de Trabalho.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\gerar_instalador.ps1
#>
[CmdletBinding()]
param(
  [string]$Saida = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'PDV Lumina')
)

$ErrorActionPreference = 'Stop'
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location $RAIZ

function Etapa {
  param([string]$Titulo)
  Write-Host ""
  Write-Host ("=" * 66) -ForegroundColor DarkCyan
  Write-Host "  $Titulo" -ForegroundColor Cyan
  Write-Host ("=" * 66) -ForegroundColor DarkCyan
}

function Falhar {
  param([string]$Msg)
  Write-Host ""
  Write-Host "FALHOU: $Msg" -ForegroundColor Red
  exit 1
}

# ---------------------------------------------------------------- 1. icone
Etapa "1/5  Icone do programa"
& "$RAIZ\.venv\Scripts\python.exe" "$RAIZ\scripts\gerar_icone.py"
if ($LASTEXITCODE -ne 0) { Falhar "nao consegui gerar o icone" }

# ------------------------------------------------------------------ 2. node
Etapa "2/5  Tela (React + Vite)"
Push-Location "$RAIZ\frontend"
if (-not (Test-Path "$RAIZ\frontend\node_modules")) {
  Write-Host "instalando dependencias do frontend (1a vez pode demorar)..."
  npm ci
  if ($LASTEXITCODE -ne 0) { Pop-Location; Falhar "npm ci falhou" }
}
npm run build
$buildFront = $LASTEXITCODE
Pop-Location
if ($buildFront -ne 0) { Falhar "npm run build falhou" }
if (-not (Test-Path "$RAIZ\frontend\dist\index.html")) {
  Falhar "frontend/dist/index.html nao foi gerado"
}

# --------------------------------------------------------------- 3. .exe
Etapa "3/5  Executavel (PyInstaller)"
& "$RAIZ\.venv\Scripts\python.exe" -m PyInstaller "$RAIZ\pdv.spec" --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Falhar "PyInstaller falhou" }

$exe = "$RAIZ\dist\PDV Lumina\PDV Lumina.exe"
if (-not (Test-Path $exe)) { Falhar "o executavel nao foi gerado em $exe" }

# ------------------------------------------------------------ 4. autoteste
Etapa "4/5  Autoteste do executavel"
$relatorio = Join-Path $env:LOCALAPPDATA 'PDV Lumina\selftest.txt'
Remove-Item $relatorio -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $exe -ArgumentList '--self-test' -PassThru -Wait
if ($p.ExitCode -ne 0) {
  if (Test-Path $relatorio) { Get-Content $relatorio | ForEach-Object { Write-Host $_ -ForegroundColor Red } }
  Falhar "o autoteste do .exe falhou (codigo $($p.ExitCode)) — nao gerar instalador"
}
if (Test-Path $relatorio) { Get-Content $relatorio | ForEach-Object { Write-Host $_ } }
Write-Host ""
Write-Host "Autoteste OK — todas as bibliotecas e recursos estao no pacote." -ForegroundColor Green

# --------------------------------------------------------- 5. instalador
Etapa "5/5  Instalador (Inno Setup)"
$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  Falhar "Inno Setup nao encontrado. Instale: winget install JRSoftware.InnoSetup"
}

$iss = "$RAIZ\scripts\PDV-Lumina.iss"
& $iscc $iss | Out-Host
if ($LASTEXITCODE -ne 0) { Falhar "Inno Setup falhou ao gerar o instalador" }

$gerado = Get-ChildItem "$RAIZ\installer\PDV-Lumina-Setup-*.exe" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $gerado) { Falhar "o instalador nao apareceu em $RAIZ\installer" }

# ----------------------------------------------------------------- entrega
Etapa "Instalador pronto"
if (-not (Test-Path $Saida)) { New-Item -ItemType Directory -Path $Saida -Force | Out-Null }
$destino = Join-Path $Saida $gerado.Name
Copy-Item $gerado.FullName $destino -Force
Copy-Item "$RAIZ\build_assets\pdv_lumina.png" (Join-Path $Saida 'PDV-Lumina.png') -Force

$mb = [math]::Round($gerado.Length / 1MB, 1)
Write-Host "Instalador: $destino  ($mb MB)" -ForegroundColor Green
Write-Host "Tambem em:  $($gerado.FullName)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Para instalar: abra o .exe, clique em Instalar e siga os passos."
Write-Host "Depois de instalar, o PDV abre na area de trabalho."