"""Rotas do primeiro acesso (sem login) — o assistente que cria o ADM.

Só existem enquanto o sistema não tem nenhum usuário ativo. Depois que o
administrador é criado, a rota `/setup/primeiro-acesso` se fecha sozinha
(devolve 409) e a tela de login assume o controle.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .deps import get_conn

router = APIRouter()

MIN_SENHA = 6


def _repo():
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    return repo


def _migrate():
    try:
        from database import migrate as M
    except ImportError:
        from src.database import migrate as M
    return M


def _perfil_usuario(u: dict) -> dict:
    try:
        from services import permissoes as P
    except ImportError:
        from src.services import permissoes as P
    return {
        "id": u["id"], "nome": u["nome"], "login": u["login"], "perfil": u["perfil"],
        "perfil_rotulo": P.PERFIS.get(u["perfil"], {}).get("rotulo", u["perfil"]),
        "permissoes": P.permissoes_de(u["perfil"]),
    }


class AdminIn(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    login: str = Field(min_length=3, max_length=30)
    senha: str = Field(min_length=MIN_SENHA, max_length=72)
    confirmar_senha: str = Field(min_length=MIN_SENHA, max_length=72)


@router.get("/setup/status")
def status(conn: sqlite3.Connection = Depends(get_conn)):
    """A tela inicial usa isso para decidir entre assistente e login."""
    M = _migrate()
    configurado = M.sistema_configurado(conn)
    carimbo = ""
    try:
        linha = conn.execute(
            "SELECT setup_concluido_em FROM configuracoes WHERE id = 1"
        ).fetchone()
        carimbo = (linha["setup_concluido_em"] if linha else "") or ""
    except sqlite3.Error:
        pass
    return {
        "configurado": configurado,
        "setup_concluido_em": carimbo,
        "versao": "2.1.0",
    }


@router.post("/setup/primeiro-acesso")
def primeiro_acesso(body: AdminIn, conn: sqlite3.Connection = Depends(get_conn)):
    """Cria o administrador e já devolve a sessão — o usuário entra direto."""
    M = _migrate()
    if M.sistema_configurado(conn):
        raise HTTPException(409, "O sistema já foi configurado. Faça login.")

    nome = (body.nome or "").strip()
    login = (body.login or "").strip().lower()
    senha = body.senha or ""

    if len(nome) < 2:
        raise HTTPException(400, "Informe o nome completo do administrador.")
    if " " in login or not login:
        raise HTTPException(400, "O login não pode ter espaços.")
    if not login.replace("_", "").replace(".", "").replace("-", "").isalnum():
        raise HTTPException(400, "Use apenas letras e números no login.")
    if len(senha) < MIN_SENHA:
        raise HTTPException(400, f"A senha precisa de pelo menos {MIN_SENHA} caracteres.")
    if senha != body.confirmar_senha:
        raise HTTPException(400, "As senhas não conferem.")
    if senha.isdigit() or senha.isalpha():
        raise HTTPException(400, "Misture letras e números na senha.")

    repo = _repo()
    try:
        usr = repo.criar_usuario(conn, nome, login, senha, "admin")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Login já cadastrado.") from None

    M.marcar_setup_concluido(conn)
    token = repo.criar_sessao(conn, usr["id"], 12)
    return {"ok": True, "token": token, "usuario": _perfil_usuario(usr)}