# PDV Lumina — Frente de caixa + Estoque + Fiscal multi-API

Fullstack local Windows: **frontend React (Lumina) + backend FastAPI + SQLite**.
Roda instalado no Windows (um `.exe`) ou direto do código-fonte.

---

## Instalar o sistema (para o cliente final)

1. Abra **`PDV-Lumina-Setup-2.1.0.exe`**.
2. Clique em **Instalar** e conclua.
3. Abra o **PDV Lumina** pelo atalho da Área de Trabalho.

**Primeira vez que abre:** aparece um assistente de configuração em 3 passos
para criar o **usuário administrador** (nome, login e senha). Depois disso o
sistema já entra direto na tela de vendas.

Não existe senha padrão. Sem administrador cadastrado ninguém entra.

Requisitos: Windows 10 ou superior (64 bits). Usa o Microsoft Edge, que já vem
no Windows.

### Onde ficam os dados

```
%LOCALAPPDATA%\PDV Lumina\
├── pdv.db          vendas, produtos, usuários, caixa, configurações
├── api.log         log da API
├── pdv.log         log do programa
└── navegador\      perfil isolado do navegador usado pelo PDV
```

Os dados **não** ficam na pasta do programa. Atualizar ou desinstalar o PDV
Lumina nunca apaga o que foi cadastrado.

### Recomeçar do zero

Feche o sistema e apague a pasta `%LOCALAPPDATA%\PDV Lumina`
(ou, no código-fonte: `python scripts\limpar_instalacao.py --sim`).
Na próxima abertura o assistente de configuração inicial aparece de novo.

---

## Gerar o instalador (máquina de build)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gerar_instalador.ps1
```

O script faz tudo em 5 etapas e **para se alguma falhar**:

| # | Etapa | O que faz |
|---|-------|-----------|
| 1 | Ícone | gera `build_assets\pdv_lumina.ico` |
| 2 | Tela | `npm run build` (React + Vite + Tailwind) |
| 3 | Executável | `PyInstaller pdv.spec` (pasta `dist\PDV Lumina\`, ~93 MB) |
| 4 | Autoteste | roda `PDV Lumina.exe --self-test` — se faltar biblioteca ou recurso, o build para aqui |
| 5 | Instalador | Inno Setup → `installer\PDV-Lumina-Setup-2.1.0.exe` (~34 MB) |

O instalador sai também na Área de Trabalho, na pasta `PDV Lumina`.
Para escolher outro destino: `-Saida "D:\algum\ lugar"`.

Requisitos da máquina de build: `.venv` com `requirements.txt`, Node.js e
Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

### Por que PyInstaller em pasta (onedir) e não `.exe` único

- não extrai ~93 MB para `%TEMP%` a cada abertura (abre muito mais rápido);
- o antivírus do Windows não fica analisando um `.exe` gigante toda vez;
- falha de biblioteca aparece no build, não na frente do cliente.

### Instalador sem-UAC

`PrivilegesRequired=lowest`: instala em `%LOCALAPPDATA%\Programs`, não pede
senha de administrador e não dispara o UAC.

### Autoteste do executável

```powershell
& ".\dist\PDV Lumina\PDV Lumina.exe" --self-test; $LASTEXITCODE
```

Importa todas as libs (FastAPI, matplotlib, reportlab, win32print…), confere
os recursos embutidos e tenta criar um banco. Relatório em
`%LOCALAPPDATA%\PDV Lumina\selftest.txt`. Código de saída 0 = tudo certo.

---

## Rodar do código-fonte (dev)

```powershell
cd D:\pdv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# terminal 1 — mock fiscal (opcional, p/ testar emissão)
node mock-sefaz\server.js          # http://localhost:3000/health

# terminal 2 — API
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# terminal 3 — frontend
cd frontend; npm install; npm run dev   # http://localhost:5173
```

Atalho: `powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1`

Para rodar o **programa** em vez dos 3 processos separados:

```powershell
.\.venv\Scripts\python.exe pdv_main.py     # sobe a API e abre a tela
```

Variáveis úteis: `PDV_PORTA=9000`, `PDV_SEM_NAVEGADOR=1` (não abre navegador),
`PDV_DB_PATH=C:\...\teste.db`.

### Primeiro acesso no dev

O banco nasce **sem nenhum usuário**, então a primeira tela é o assistente de
configuração (mesmo caminho do `.exe`). A partir daí é a tela de login.

---

## Estrutura

```
D:\pdv\
├── frontend\               React + Vite + Tailwind
│   ├── src\App.tsx         vendas/estoque/histórico/relatórios/pessoas/config
│   │                       + LoginScreen + SetupWizardScreen (primeiro acesso)
│   ├── src\api.ts          fetch /api + cliente do assistente de 1º acesso
│   └── vite.config.ts      base './' (funciona em file:// e rede local)
├── src\
│   ├── api\                FastAPI: app.py + routes_* (inclui routes_setup.py)
│   ├── core\               paths.py (dados no %LOCALAPPDATA%) e ciclo.py (sair)
│   ├── database\           schema.sql + migrate.py + repositories.py
│   ├── services\           impressão, PDF, gráficos, fiscal, permissões
│   └── ui\                 legado PySide6 (só referência — não é empacotado)
├── pdv_main.py             entrada do .exe: instância única, porta, navegador
├── pdv.spec                configuração do PyInstaller
├── scripts\PDV-Lumina.iss  instalador (Inno Setup 6)
├── scripts\gerar_instalador.ps1   build completo em 5 etapas
└── data\pdv.db             banco local no dev (não vai pro Git)
```

Em desenvolvimento o banco fica em `data\pdv.db`. No `.exe` instalado, em
`%LOCALAPPDATA%\PDV Lumina\pdv.db` (ver `src\core\paths.py`).

---

## Primeiro acesso (assistente)

Aparece só enquanto o sistema não tem nenhum usuário ativo
(`migrate.sistema_configurado`). Passos:

1. **Boas-vindas** — o que você precisa ter em mãos.
2. **Administrador** — nome, login, senha e repetir a senha (mín. 6 caracteres,
   letras + números).
3. **Pronto** — conferência dos dados e abertura do sistema.

Depois de criado, `POST /api/setup/primeiro-acesso` se fecha sozinha (409).

Regras de senha: mínimo 6 caracteres, precisa misturar letras e números, não
pode ser só números nem só letras. A senha é guardada com PBKDF2-HMAC-SHA256
(120.000 iterações, salt aleatório) — nunca em texto puro.

---

## Fiscal — 5 APIs separadas (testar, depois manter só a oficial)

Aba **Configurações → Fiscal e emissão**. Provedor ativo em
`configuracoes.fiscal_provider`:

| # | Provedor | Config | Teste |
|---|----------|--------|-------|
| 1 | Mock Local | `mock_url` (default `http://localhost:3000`) | `GET /health` do mock |
| 2 | Nuvem Fiscal | `nuvem_token` + `nuvem_url` (Bearer) | valida token+https |
| 3 | Focus NFe | `focus_token` + `focus_url` (Basic) | valida token |
| 4 | SEFAZ Direta | `sefaz_cert_path` (.pfx A1) | checa arquivo existe |
| 5 | Custom | `custom_url` + `custom_token` (legado `api_nfce_*`) | valida URL |

Checkout (`POST /api/vendas`) dispara emissão em **background** (nunca bloqueia
o caixa).

---

## API (resumo)

Rotas liberadas (sem login):
`/api/health`, `/api/meta`, `/api/auth/login`, `/api/auth/perfis`,
`/api/setup/status`, `/api/setup/primeiro-acesso`, `/api/sistema/encerrar`.

Tudo o mais exige `Authorization: Bearer <token>`.

- Produtos: `GET /api/produtos`, `GET /api/produtos/busca?termo=`, `POST/PUT/DELETE /api/produtos/{id}`
- Usuários: `GET/POST /api/usuarios`, `PUT/DELETE /api/usuarios/{id}` (só admin)
- Caixa: `GET /api/caixa/aberto`, `POST /api/caixa/abrir|fechar|operacao`
- Vendas: `POST /api/vendas` (com `desconto_percentual`), `GET /api/vendas`,
  `GET /api/vendas/totais?dia=`, `POST /api/vendas/{id}/cancelar`
- Relatórios: `GET /api/relatorios/diario|semanal|mensal`, `POST /api/relatorios/gerar-pdf`

---

## Acesso (login)

| Perfil | Acesso |
|---|---|
| `admin` | tudo (`*`) |
| `operador` | vendas, caixa, consultar estoque/validade, histórico e relatórios |

```powershell
.\.venv\Scripts\python.exe scripts\reset_usuarios.py --listar              # só lista
.\.venv\Scripts\python.exe scripts\reset_usuarios.py --senha "Nova123"     # recria o ADM
.\.venv\Scripts\python.exe scripts\reset_usuarios.py --zerar               # apaga todos
```

`--zerar` faz o assistente de configuração inicial voltar a aparecer.

---

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v   # 46 testes
cd frontend; npm run build                                       # tsc + vite build
```

---

## Notas técnicas

- **Sem webfont externa.** O frontend usa a fonte do Windows (Segoe UI) em vez
  do Google Fonts: o PDV instalado roda em rede fechada e não pode esperar o
  CDN carregar.
- **Impressão térmica** via `win32print`/RAW (pywin32). O `python-escpos` não é
  mais dependência — não era usado em lugar nenhum do código.
- **Instância única** via mutex do Windows (`Local\PDVLuminaMutex`, sem
  privilégio de administrador). Clicar 2x no ícone reabre a janela em vez de
  subir um segundo servidor.
- **Encerrar** pelo botão *Configurações → Encerrar o sistema* grava um
  arquivo sentinela que o `pdv_main.py` vigia. Arquivo em disco (e não um
  `threading.Event`) porque dentro do `.exe` o mesmo módulo pode acabar
  importado sob dois nomes, e aí cada cópia teria seu próprio estado.
- **A API só escuta `127.0.0.1`.** Não é exposta na rede.