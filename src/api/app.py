"""App FastAPI do PDV Lumina — serve o front React + SQLite local."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3
import sys
import time
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
ROOT = SRC.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "data"
LOG_FILE = LOG_DIR / "api.log"
LIMITE_LOG = 2_000_000  # 2 MB — rotaciona para api.log.1


def _log_dir():
    """No .exe o log vai para %LOCALAPPDATA% (nunca ao lado do programa)."""
    try:
        from core.paths import caminho_log
    except ImportError:
        from src.core.paths import caminho_log
    return caminho_log("api.log").parent


def registrar(mensagem: str) -> None:
    """Escreve no log da API (e nunca levanta erro por causa do log)."""
    try:
        pasta = _log_dir()
        pasta.mkdir(parents=True, exist_ok=True)
        log = caminho_log_atual()
        if log.exists() and log.stat().st_size > LIMITE_LOG:
            log.replace(pasta / "api.log.1")
        from datetime import datetime
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')} {mensagem}\n")
    except Exception:
        pass


def caminho_log_atual():
    try:
        from core.paths import caminho_log
        return caminho_log("api.log")
    except ImportError:
        from src.core.paths import caminho_log
        return caminho_log("api.log")


def _montar_frontend(app: FastAPI) -> None:
    """No programa instalado o frontend buildado vem embutido e é servido aqui.

    O front chama '/api' (caminho relativo), então servir a tela e a API na
    MESMA origem dispensa CORS, dispensa proxy e funciona sem internet.
    """
    try:
        from core.paths import caminho_web
    except ImportError:
        from src.core.paths import caminho_web
    web = caminho_web()
    index = web / "index.html"
    if not index.is_file():
        registrar(f"Frontend embutido ausente em {web}")
        return

    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    assets = web / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
    registrar(f"Frontend embutido servido de {web}")
    raiz = web.resolve()

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        if caminho.startswith("api/"):
            return JSONResponse({"detail": "Rota não encontrada."}, status_code=404)
        alvo = (web / caminho).resolve()
        if caminho and alvo.is_relative_to(raiz) and alvo.is_file():
            return FileResponse(str(alvo))
        # qualquer rota desconhecida cai no index (SPA)
        return FileResponse(str(index))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.schema import init_db
    init_db()
    registrar("API iniciada")
    yield
    registrar("API encerrada")


def create_app() -> FastAPI:
    app = FastAPI(title="PDV Lumina API", version="2.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .auth import montar_middleware
    montar_middleware(app)

    # ---- log de requisições + erros sempre em data/api.log ----
    @app.middleware("http")
    async def _log_requests(request: Request, call_next):
        inicio = time.perf_counter()
        try:
            resposta = await call_next(request)
        except Exception as e:
            ms = (time.perf_counter() - inicio) * 1000
            registrar(f"ERRO500 {request.method} {request.url.path} "
                      f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            return JSONResponse(
                {"detail": f"Falha interna ({type(e).__name__}). Veja data/api.log.",
                 "erro": uuid.uuid4().hex[:8]},
                status_code=500,
            )
        ms = (time.perf_counter() - inicio) * 1000
        if request.url.path.startswith("/api"):
            registrar(f"{resposta.status_code} {request.method} {request.url.path} {ms:.0f}ms")
        return resposta

    @app.exception_handler(sqlite3.OperationalError)
    async def _erro_banco(request: Request, exc: sqlite3.OperationalError):
        registrar(f"ERRO_BANCO {request.url.path}: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            {"detail": "Banco de dados ocupado. Tente novamente em alguns instantes."},
            status_code=503,
        )

    from .routes_auth import router as auth_router
    from .routes_usuarios import router as usuarios_router
    from .routes_produtos import router as produtos_router
    from .routes_caixa import router as caixa_router
    from .routes_vendas import router as vendas_router
    from .routes_config import router as config_router
    from .routes_fiscal import router as fiscal_router
    from .routes_relatorios import router as relatorios_router
    from .routes_setup import router as setup_router

    app.include_router(setup_router, prefix="/api", tags=["setup"])
    app.include_router(auth_router, prefix="/api", tags=["auth"])
    app.include_router(usuarios_router, prefix="/api", tags=["usuarios"])
    app.include_router(produtos_router, prefix="/api", tags=["produtos"])
    app.include_router(caixa_router, prefix="/api", tags=["caixa"])
    app.include_router(vendas_router, prefix="/api", tags=["vendas"])
    app.include_router(config_router, prefix="/api", tags=["config"])
    app.include_router(fiscal_router, prefix="/api", tags=["fiscal"])
    app.include_router(relatorios_router, prefix="/api", tags=["relatorios"])

    @app.get("/api/health")
    def health():
        from database.schema import table_counts
        try:
            return {"status": "ok", "banco": table_counts()}
        except Exception as e:
            registrar(f"HEALTH falhou: {e}\n{traceback.format_exc()}")
            return JSONResponse({"status": "erro", "detalhe": str(e)}, status_code=503)

    @app.get("/api/meta")
    def meta():
        try:
            from services.fiscal_providers import PROVIDER_CHOICES
        except ImportError:
            from src.services.fiscal_providers import PROVIDER_CHOICES
        return {
            "app": "PDV Lumina",
            "versao": "2.1.0",
            "categorias": ["Bebidas", "Alimentos", "Padaria", "Higiene"],
            "pagamentos": ["credito", "debito", "pix", "dinheiro"],
            "providers_fiscais": PROVIDER_CHOICES,
        }

    @app.post("/api/sistema/encerrar")
    def encerrar():
        """Botão 'Sair do sistema'. O uvicorn só escuta 127.0.0.1, então
        só um processo nesta máquina consegue chamar."""
        try:
            from core.ciclo import pedir_encerramento
        except ImportError:
            from src.core.ciclo import pedir_encerramento
        pedir_encerramento()
        registrar("Encerramento pedido pela interface")
        return {"ok": True}

    @app.get("/api/sistema/versao")
    def versao():
        return {"versao": "2.1.0", "python": sys.version.split()[0]}

    _montar_frontend(app)

    return app


app = create_app()
