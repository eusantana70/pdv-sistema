"""Rotas de usuários (pessoas) e perfis de acesso — somente admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import exige
from .deps import get_conn

router = APIRouter(dependencies=[Depends(exige("usuarios"))])


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


class UsuarioIn(BaseModel):
    nome: str
    login: str
    senha: str = Field(default="")
    perfil: str = "operador"


class UsuarioPatch(BaseModel):
    nome: str | None = None
    perfil: str | None = None
    ativo: int | None = None
    senha: str | None = None


@router.get("/usuarios")
def listar(conn=Depends(get_conn)):
    return _repo().listar_usuarios(conn)


@router.post("/usuarios", status_code=201)
def criar(body: UsuarioIn, conn=Depends(get_conn)):
    try:
        return _repo().criar_usuario(conn, body.nome, body.login, body.senha, body.perfil)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/usuarios/{usuario_id}")
def atualizar(usuario_id: int, body: UsuarioPatch, conn=Depends(get_conn)):
    repo = _repo()
    atual = repo.obter_usuario(conn, usuario_id)
    if not atual:
        raise HTTPException(404, "Usuário não encontrado.")
    try:
        return repo.atualizar_usuario(
            conn, usuario_id,
            body.nome if body.nome is not None else atual["nome"],
            body.perfil if body.perfil is not None else atual["perfil"],
            int(atual["ativo"]) if body.ativo is None else int(body.ativo),
            body.senha or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/usuarios/{usuario_id}", status_code=204)
def excluir(usuario_id: int, conn=Depends(get_conn)):
    try:
        _repo().excluir_usuario(conn, usuario_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return None