# Build do executável único com PyInstaller (máquina de build, não do cliente).
# Requer: pip install -r requirements.txt  (PyInstaller incluso)
# Saída: dist\PDV-Sorvetes.exe (arquivo único, --onefile, --windowed)
# O banco data\pdv.db é criado na primeira execução (não embutido com dados).
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if (-not (Test-Path "src\main.py")) { throw "src\main.py não encontrado" }

pyinstaller --noconfirm --clean `
  --name "PDV-Sorvetes" `
  --onefile --windowed `
  --add-data "src\database\schema.sql;src\database" `
  --paths "src" `
  --collect-all "PySide6" `
  src\main.py

Write-Host "`nOK: dist\PDV-Sorvetes.exe gerado. Teste em máquina limpa antes de distribuir."
Write-Host "Próximo passo (opcional): compilar instalador com Inno Setup usando scripts\installer.iss"
