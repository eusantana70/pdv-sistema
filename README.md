# PDV Sistema — Sorvetes (Franquia MG)

Desktop autônomo Windows: **Python + PySide6 + SQLite** (arquivo único `data/pdv.db`).
Sem servidor externo. Instalador final: **PyInstaller → .exe único → Inno Setup → Setup.exe**.

## Stack decidida

| Camada | Escolha | Por quê |
|---|---|---|
| UI | PySide6 (Qt6) | Moderna, responsiva, `pip install` único, empacota bem no PyInstaller |
| DB | SQLite (stdlib `sqlite3`) | Arquivo único local, zero instalação no cliente |
| Build | PyInstaller `--onefile --windowed` | Embute Python + PySide6 + libs no .exe |
| Instalador | Inno Setup 6 | Gera `PDV-Sorvetes-Setup.exe` com atalho |
| Fiscal/HTTP | `requests` (background thread) | POST assíncrono p/ Nuvem Fiscal / Focus NFe |
| Impressão | `pywin32` + `python-escpos` | Térmica via `win32print`/ESC-POS + QR |

## Estrutura

```
D:\pdv\
├── src\
│   ├── main.py                  # entry point (cria DB se não existir)
│   ├── database\connection.py   # PRAGMA FK+WAL, data\pdv.db
│   ├── database\schema.sql      # 8 tabelas (fonte oficial do schema)
│   ├── database\schema.py       # init_db()
│   ├── services\codigo_interno.py  # 4 dígitos únicos
│   ├── services\pagamentos.py      # split + troco
│   ├── services\fiscal_payload.py  # JSON NFC-e
│   └── ui\                      # telas (próximo passo)
├── scripts\
│   ├── init_db.py      # python scripts\init_db.py (stdlib, já rodado)
│   ├── build_exe.ps1   # gera dist\PDV-Sorvetes.exe
│   └── installer.iss   # receita do Setup.exe (Inno Setup)
├── data\pdv.db         # criado local, NÃO vai pro Git
├── tests\test_basico.py
└── requirements.txt
```

Banco validado: 8 tabelas criadas, `configuracoes(id=1)` seed OK.

## Ambiente — ESCOLHA ONDE INSTALAR (aguardando sua decisão)

Nada de terceiros foi instalado ainda. Só usei Python 3.14 + SQLite da sua máquina.

**Opção A — venv na pasta do projeto (recomendado p/ dev):**
```powershell
cd D:\pdv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\init_db.py
python -m unittest discover -s tests -v
python src\main.py
```
Baixa ~350 MB (Qt6) para `D:\pdv\.venv\` (isolado, não suja o PC).

**Opção B — global no PC:**
```powershell
cd D:\pdv
pip install -r requirements.txt
python scripts\init_db.py
python src\main.py
```
Mesmos ~350 MB em `C:\Python314\Lib\site-packages\` (vale p/ todos os projetos).

## Build .exe (só após aprovar UI)

```powershell
# 1. com venv ativo:
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
# saída: dist\PDV-Sorvetes.exe (~60-90 MB, Python+Qt embutidos, sem pedir Python no cliente)

# 2. (opcional) abrir scripts\installer.iss no Inno Setup > Compile
# saída: installer\PDV-Sorvetes-Setup.exe
```

Cliente final não instala Python, Node ou SQL — só roda o Setup.exe.

## Módulos (status)

- [x] Base: schema 8 tabelas + `data/pdv.db` + testes split/código interno
- [x] M1 Config (token/URL/impressora) + Perfis Fiscais (NCM/CFOP/CSOSN)
- [x] M2 Estoque grid rápido (Enter adiciona, código 4 dígitos, desconto %, busca)
- [x] M3 Caixa (abrir/fechar/sangria/suprimento + saldo previsto)
- [x] M4 Frente de caixa (autocomplete nome/código, carrinho, gate caixa aberto)
- [x] M5 Modal pagamento (split N formas, crédito 1–12x, troco só dinheiro)
- [x] M6 Fiscal async (POST background, link/XML) + impressão térmica + pergunta cupom
- [x] M7 Histórico (cancelar c/ estorno + comando API, reimprimir, totais do dia)

Testes: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` (28 testes).
