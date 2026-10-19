"""Autenticação e autorização por permissão."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import HTTPException, Request

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# rotas liberadas (sem login)
PUBLICAS = {
    "/api/health",
    "/api/meta",
    "/api/auth/login",
    "/api/auth/perfis",
    # primeiro acesso: o próprio assistente precisa delas para criar o ADM.
    # /setup/primeiro-acesso se fecha sozinha quando já existe usuário ativo.
    "/api/setup/status",
    "/api/setup/primeiro-acesso",
    # desligar o PDV pela interface (servidor só escuta 127.0.0.1)
    "/api/sistema/encerrar",
}


def _perms():
    try:
        from services import permissoes as P
        return P
    except ImportError:
        from src.services import permissoes as P
        return P


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


def token_da_requisicao(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Auth-Token", "").strip()


def usuario_atual(request: Request) -> dict | None:
    """Usuário da requisição (None se rota pública ou token inválido)."""
    u = getattr(request.state, "usuario", None)
    return u


def exige(chave: str):
    """Dependência que bloqueia quem não tem a permissão."""
    def _dep(request: Request) -> dict:
        u = getattr(request.state, "usuario", None)
        if not u:
            raise HTTPException(401, "Faça login para continuar.")
        P = _perms()
        if not P.pode(u.get("perfil", "operador"), chave):
            raise HTTPException(403, "Seu perfil não tem acesso a esta função.")
        return u
    return _dep


def montar_middleware(app):
    """Exige login em todas as rotas /api exceto as públicas."""
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def _auth(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api") and path not in PUBLICAS:
            token = token_da_requisicao(request)
            if token:
                try:
                    from database.connection import connect, get_db_path
                    conn = connect(get_db_path())
                    try:
                        u = _repo().usuario_do_token(conn, token)
                    finally:
                        conn.close()
                except Exception:
                    u = None
                if not u:
                    return JSONResponse({"detail": "Sessão expirada. Faça login novamente."}, status_code=401)
                request.state.usuario = u
                request.state.token = token
            elif path.startswith("/api/auth/me"):
                return JSONResponse({"detail": "Faça login para continuar."}, status_code=401)
        return await call_next(request)
    return app