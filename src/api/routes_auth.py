"""Rotas de autenticação: login, sessão atual e saída."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .deps import get_conn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


def _perms():
    try:
        from services import permissoes as P
        return P
    except ImportError:
        from src.services import permissoes as P
        return P


class LoginIn(BaseModel):
    login: str
    senha: str = Field(min_length=1)


def _perfil_usuario(u: dict) -> dict:
    P = _perms()
    return {
        "id": u["id"], "nome": u["nome"], "login": u["login"], "perfil": u["perfil"],
        "perfil_rotulo": P.PERFIS.get(u["perfil"], {}).get("rotulo", u["perfil"]),
        "permissoes": P.permissoes_de(u["perfil"]),
    }


@router.post("/auth/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    repo = _repo()
    usr = repo.autenticar(conn, body.login, body.senha)
    if not usr:
        raise HTTPException(401, "Login ou senha inválidos.")
    try:
        cfg = repo.obter_config_full(conn)
    except Exception:
        cfg = {}
    token = repo.criar_sessao(conn, usr["id"], int(cfg.get("sessao_horas") or 12))
    return {"token": token, "usuario": _perfil_usuario(usr)}


@router.get("/auth/me")
def me(request: Request):
    u = getattr(request.state, "usuario", None)
    if not u:
        raise HTTPException(401, "Sessão expirada. Faça login novamente.")
    return _perfil_usuario(u)


@router.get("/auth/perfis")
def perfis():
    P = _perms()
    return {"perfis": P.lista_perfis(), "permissoes": P.PERMISSOES}


@router.post("/auth/logout")
def logout(request: Request, conn=Depends(get_conn)):
    _repo().encerrar_sessao(conn, getattr(request.state, "token", ""))
    return {"ok": True}