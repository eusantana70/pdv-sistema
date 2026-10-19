"""Rotas de caixa — abertura/fechamento/sangria/suprimento/saldo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .auth import exige
from .deps import get_conn
from .schemas import CaixaAbrir, CaixaFechar, CaixaOperacao

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


@router.get("/caixa/aberto", dependencies=[Depends(exige("caixa"))])
def caixa_aberto(conn=Depends(get_conn)):
    repo = _repo()
    mov = repo.obter_caixa_aberto(conn)
    ultimo = None
    try:
        ultimo = repo.obter_ultimo_fechado(conn)
    except Exception:
        ultimo = None
    if not mov:
        return {"aberto": False, "movimento": None, "ultimo_fechado": ultimo}
    try:
        saldo = repo.saldo_previsto_caixa(conn, mov["id"])
    except Exception:
        saldo = float(mov.get("valor_inicial") or 0)
    return {"aberto": True, "movimento": mov, "saldo_previsto": saldo,
            "ultimo_fechado": ultimo}


@router.post("/caixa/abrir", status_code=201, dependencies=[Depends(exige("caixa"))])
def abrir(body: CaixaAbrir, conn=Depends(get_conn)):
    repo = _repo()
    try:
        return repo.abrir_caixa(conn, body.valor_inicial)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/caixa/fechar", dependencies=[Depends(exige("caixa"))])
def fechar(body: CaixaFechar, conn=Depends(get_conn)):
    repo = _repo()
    try:
        repo.fechar_caixa(conn, body.movimento_id, body.valor_final)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/caixa/operacao", status_code=201, dependencies=[Depends(exige("caixa"))])
def operacao(body: CaixaOperacao, conn=Depends(get_conn)):
    repo = _repo()
    try:
        oid = repo.adicionar_operacao(conn, body.id_movimento, body.tipo, body.valor, body.observacao)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": oid, "saldo_previsto": repo.saldo_previsto_caixa(conn, body.id_movimento)}


@router.get("/caixa/movimentos", dependencies=[Depends(exige("caixa"))])
def movimentos(limite: int = 50, conn=Depends(get_conn)):
    return _repo().listar_movimentos(conn, limite)


@router.get("/caixa/{movimento_id}/saldo")
def saldo(movimento_id: int, conn=Depends(get_conn)):
    try:
        return {"saldo_previsto": _repo().saldo_previsto_caixa(conn, movimento_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/caixa/{movimento_id}/operacoes")
def operacoes(movimento_id: int, conn=Depends(get_conn)):
    return _repo().listar_operacoes(conn, movimento_id)


@router.get("/caixa-operacoes", dependencies=[Depends(exige("caixa"))])
def operacoes_dia(dia: str = "", limite: int = 200, conn=Depends(get_conn)):
    """Histórico de sangrias/suprimentos (dia='YYYY-MM-DD'; vazio = todos)."""
    return _repo().listar_operacoes_dia(conn, dia, limite)
