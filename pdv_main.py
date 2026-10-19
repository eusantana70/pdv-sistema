"""Ponto de entrada do PDV Lumina instalado (empacotado pelo PyInstaller).

O que este arquivo faz:
1. garante instância única (mutex do Windows) — clicar 2x no ícone não abre 2 PDVs;
2. escolhe uma porta livre e sobe a API (FastAPI/uvicorn) em uma thread;
3. abre a tela em modo aplicativo (Edge/Chrome --app), sem barra de endereço;
4. fica segurando o processo até o usuário pedir "Sair do sistema".

Em modo desenvolvimento (sem congelar) roda igual, então dá para testar o
caminho de instalação sem instalar nada.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# matplotlib precisa saber que não há display antes de qualquer import.
os.environ.setdefault("MPLBACKEND", "Agg")

RAIZ = Path(__file__).resolve().parent
for _p in (RAIZ / "src", RAIZ):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# O .exe é compilado sem console (console=False). Quando o Windows inicia um
# programa desses pelo Explorer/atalho, nao existe console nenhum e o Python
# deixa sys.stdout/sys.stderr como None. O uvicorn, ao montar o formatter do
# log, chama sys.stdout.isatty() e estoura um AttributeError — o PDV nao
# subia de jeito nenhum. Apontar para o null device resolve e nao atrapalha
# nada quando ha console (dev).
for _fluxo in ("stdout", "stderr"):
    if getattr(sys, _fluxo, None) is None:
        try:
            setattr(sys, _fluxo, open(os.devnull, "w", encoding="utf-8"))
        except Exception:
            pass

try:
    from core import ciclo
    from core.paths import APP_NOME, MUTEX, caminho_log, data_dir
except ImportError:
    from src.core import ciclo
    from src.core.paths import APP_NOME, MUTEX, caminho_log, data_dir

PORTA_INICIAL = 8770
TIMEOUT_ABERTURA = 45  # segundos esperando a API responder
ARQ_PORTA = "pdv.json"

_mutex_handle = None  # mantém vivo o handle (se for GC, o mutex some)


def _log(msg: str) -> None:
    try:
        with caminho_log().open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


# --------------------------------------------------------------------------
# instância única
# --------------------------------------------------------------------------
def _primeira_instancia() -> bool:
    """True se ninguém mais está com o PDV aberto."""
    global _mutex_handle
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _mutex_handle = kernel32.CreateMutexW(None, True, MUTEX)
        if not _mutex_handle:
            # sem mutex o PDV abre normalmente — melhor do que travar
            return True
        return ctypes.get_last_error() != 183  # 183 = ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _arquivo_porta():
    return data_dir() / ARQ_PORTA


def _ler_porta_salva() -> int | None:
    try:
        return int(json.loads(_arquivo_porta().read_text(encoding="utf-8"))["porta"])
    except Exception:
        return None


def _salvar_porta(porta: int) -> None:
    try:
        _arquivo_porta().write_text(
            json.dumps({"porta": porta, "pid": os.getpid()}), encoding="utf-8"
        )
    except Exception:
        pass


def _apagar_arquivo_porta() -> None:
    try:
        _arquivo_porta().unlink(missing_ok=True)
    except Exception:
        pass


# --------------------------------------------------------------------------
# porta e navegador
# --------------------------------------------------------------------------
def _porta_livre(inicio: int = PORTA_INICIAL, tentativas: int = 40) -> int:
    for i in range(tentativas):
        porta = inicio + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    return 0  # 0 = deixa o sistema operacional escolher


def _porta_desejada() -> int:
    """PDV_PORTA=9000 fixa a porta (terminal em quiosque / teste automatizado)."""
    bruta = os.environ.get("PDV_PORTA", "").strip()
    if bruta.isdigit():
        return int(bruta)
    return _porta_livre()


def _navegadores() -> list[str]:
    """Caminhos do Edge/Chrome — navegadores que já vêm no Windows."""
    bases = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    rel = [
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    achados: list[str] = []
    for base in bases:
        if not base:
            continue
        for r in rel:
            p = Path(base) / r
            if p.is_file() and str(p) not in achados:
                achados.append(str(p))
    return achados


def _abrir_tela(url: str) -> None:
    """Abre a tela do PDV. Preferência: Edge/Chrome em modo aplicativo."""
    import subprocess

    perfil = data_dir() / "navegador"
    args = [
        f"--app={url}",
        f"--user-data-dir={perfil}",
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,MediaRouter",
    ]
    for exe in _navegadores():
        try:
            # lista de argumentos: o Windows escapa as aspas do caminho do exe
            subprocess.Popen([exe, *args], close_fds=True)
            _log(f"Tela aberta em {exe}")
            return
        except Exception as e:
            _log(f"Falha ao abrir {exe}: {e}")
    try:
        webbrowser.open(url)
        _log("Tela aberta no navegador padrão")
    except Exception as e:
        _log(f"Não consegui abrir o navegador: {e}")


def _esperar_api(porta: int, timeout: int = TIMEOUT_ABERTURA) -> bool:
    url = f"http://127.0.0.1:{porta}/api/health"
    fim = time.time() + timeout
    while time.time() < fim:
        if ciclo.aguardando_encerramento():
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except urllib.error.HTTPError:
            return True  # respondeu, mesmo com erro
        except Exception:
            time.sleep(0.35)
    return False


# --------------------------------------------------------------------------
# servidor
# --------------------------------------------------------------------------
def _servir(porta: int) -> tuple[object, threading.Thread]:
    import uvicorn

    from api.app import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=porta,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=15,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="pdv-api", daemon=True)
    thread.start()
    return server, thread


def _falhar(mensagem: str) -> None:
    """Erro fatal: mostra numa janela e grava o traceback no log."""
    detalhe = ""
    if sys.exc_info()[0] is not None:
        detalhe = "\n\n" + "".join(traceback.format_exception(*sys.exc_info()))
    _log("FALHA: " + mensagem + detalhe)
    texto = f"{mensagem}{detalhe}\n\nDetalhes em:\n{caminho_log()}"
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, texto, APP_NOME, 0x10)
    except Exception:
        pass
    print("FALHA: " + texto, file=sys.stderr)


def _teste_proprio() -> int:
    """Confere se o pacote empacotado tem tudo que o sistema precisa.

    Roda no build logo depois de gerar o .exe — se faltar biblioteca, DLL ou
    arquivo de recurso, aparece aqui em vez de na frente do cliente.
    """
    from api.app import app as app_importado

    os.environ.setdefault("MPLCONFIGDIR", str(data_dir() / "mplcache"))
    linhas: list[str] = []
    ok = True

    def saida(texto: str) -> None:
        print(texto)
        linhas.append(texto)

    modulos = [
        "sqlite3", "fastapi", "pydantic", "uvicorn", "starlette",
        # o uvicorn.Config importa estes na hora de montar o servidor
        "uvicorn.logging", "uvicorn.config", "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto", "uvicorn.lifespan.on",
        "logging.config",
        # monta um Config de verdade: e o que estourava no .exe
        "click",
        "core.paths", "core.ciclo",
        "database.connection", "database.schema", "database.migrate",
        "database.repositories",
        "services.permissoes", "services.impressao", "services.arquivos_fiscais",
        "services.fiscal_providers", "services.graficos", "services.pdf",
        "services.relatorio_pdf",
        "api.app", "api.auth", "api.deps", "api.routes_setup", "api.routes_auth",
        "api.routes_usuarios", "api.routes_produtos", "api.routes_caixa",
        "api.routes_vendas", "api.routes_config", "api.routes_fiscal",
        "api.routes_relatorios",
        # relatorios em PDF com grafico e impressao termica sao parte do produto
        "matplotlib.pyplot", "reportlab.platypus",
        "qrcode", "requests", "win32print",
    ]
    for m in modulos:
        try:
            __import__(m)
            saida(f"  ok      {m}")
        except Exception as e:
            ok = False
            saida(f"  FALHOU  {m}: {type(e).__name__}: {e}")

    saida("")
    saida("  opcionais (ausencia nao quebra o PDV):")
    for m in ("PIL.Image", "numpy"):
        try:
            __import__(m)
            saida(f"  ok      {m}")
        except Exception as e:
            saida(f"  ausente {m}: {type(e).__name__}")

    from core.paths import caminho_db, caminho_log, caminho_web
    web = caminho_web()
    saida("")
    saida(f"  frontend embutido: {web} -> {'ok' if (web / 'index.html').is_file() else 'FALTOU'}")
    ok = ok and (web / "index.html").is_file()

    try:
        from database.schema import _schema_file
        arq = _schema_file()
        saida(f"  schema.sql: {arq} -> {'ok' if arq.is_file() else 'FALTOU'}")
        ok = ok and arq.is_file()
    except Exception as e:
        ok = False
        saida(f"  schema.sql: FALHOU {e}")

    try:
        import tempfile

        from database.schema import init_db
        alvo = Path(tempfile.gettempdir()) / "pdv_selftest.db"
        for sufixo in ("", "-wal", "-shm"):
            Path(str(alvo) + sufixo).unlink(missing_ok=True)
        init_db(alvo)
        saida(f"  banco de teste criado: {'ok' if alvo.is_file() else 'FALHOU'}")
        ok = ok and alvo.is_file()
        for sufixo in ("", "-wal", "-shm"):
            Path(str(alvo) + sufixo).unlink(missing_ok=True)
    except Exception as e:
        ok = False
        saida(f"  banco de teste: FALHOU {type(e).__name__}: {e}")

    saida(f"  pasta de dados:   {data_dir()}")
    saida(f"  banco do sistema: {caminho_db()}")

    # o mesmo caminho que o pdv_main usa para subir o servidor
    try:
        import uvicorn

        uvicorn.Config(app_importado, host="127.0.0.1", port=0,
                       log_level="warning", access_log=False)
        saida("  uvicorn.Config montado: ok")
    except Exception as e:
        ok = False
        saida(f"  uvicorn.Config: FALHOU {type(e).__name__}: {e}")
        saida("".join(traceback.format_exc()))

    saida(f"  sys.stdout: {'ok' if sys.stdout is not None else 'NONE (seria um erro)'}")
    ok = ok and sys.stdout is not None
    saida(f"  log:              {caminho_log()}")
    saida("")
    saida("AUTOTESTE OK" if ok else "AUTOTESTE COM FALHAS")
    # o .exe e windowed (sem console): o relatorio vai para arquivo
    try:
        caminho_log("selftest.txt").write_text("\n".join(linhas), encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", str(data_dir() / "mplcache"))
    if "--self-test" in sys.argv:
        return _teste_proprio()
    if not _primeira_instancia():
        # já está aberto: só traz a janela de volta para a frente
        porta = _ler_porta_salva()
        if porta:
            _log(f"Já em execução (porta {porta}) — reabrindo a tela")
            _abrir_tela(f"http://127.0.0.1:{porta}/")
            return 0
        _log("Outra instância detectada, sem porta salva — encerrando")
        return 0

    porta = _porta_desejada()
    if porta <= 0:
        _falhar("Não foi possível reservar uma porta local para o PDV.")
        return 1
    ciclo.limpar()  # ignora pedido de encerrar que sobrou de uma queda
    _log(f"Iniciando {APP_NOME} na porta {porta}")
    _salvar_porta(porta)

    try:
        server, thread = _servir(porta)
    except Exception as e:
        _apagar_arquivo_porta()
        _falhar(f"Não consegui iniciar o sistema:\n{e}")
        return 1

    if not _esperar_api(porta):
        server.should_exit = True
        _apagar_arquivo_porta()
        _falhar("O sistema demorou demais para responder e foi encerrado.")
        return 1

    _log("Sistema pronto")
    # PDV_SEM_NAVEGADOR=1 não abre nada (terminal já mostra a URL, ou teste)
    if os.environ.get("PDV_SEM_NAVEGADOR", "").strip() not in ("1", "true", "sim"):
        _abrir_tela(f"http://127.0.0.1:{porta}/")
    else:
        print(f"PDV Lumina em http://127.0.0.1:{porta}/")

    # segura o processo enquanto o PDV estiver aberto
    ciclo.esperar_encerramento()
    _log("Encerrando a API")
    server.should_exit = True
    thread.join(timeout=10)
    _apagar_arquivo_porta()
    _log("PDV encerrado")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)