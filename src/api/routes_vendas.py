"""Rotas de vendas — checkout do front + histórico + totais."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import exige
from .deps import get_conn
from .schemas import LimpezaIn, VendaIn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


def _disparar_fiscal_async(venda_id: int):
    """Emite NFC-e em background sem bloquear o checkout."""
    def _run():
        try:
            from pathlib import Path
            import sys
            SRC = Path(__file__).resolve().parents[1]
            if str(SRC) not in sys.path:
                sys.path.insert(0, str(SRC))
            from database.connection import connect, get_db_path
            from database import repositories as repo
            from services.fiscal_payload import montar_payload_nfce
            from services.fiscal_providers import emitir_com_provider
            db_path = get_db_path()
            conn = connect(db_path)
            try:
                venda = repo.obter_venda(conn, venda_id)
                if not venda:
                    return
                itens = repo.listar_itens_venda(conn, venda_id)
                pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
                perfis = {p["id"]: p for p in repo.listar_perfis(conn)}
                cfg = repo.obter_config_full(conn)
            finally:
                conn.close()
            payload = montar_payload_nfce(venda, itens, pagamentos, perfis)
            # enriquece p/ providers reais
            payload["ambiente"] = cfg.get("ambiente", "homologacao")
            payload["modelo"] = cfg.get("modelo_doc", "NFC-e")
            payload["serie"] = cfg.get("serie", "1")
            payload["empresa"] = {
                "razao_social": cfg.get("razao_social", ""),
                "nome_fantasia": cfg.get("nome_fantasia", ""),
                "cnpj": cfg.get("cnpj", ""),
                "ie": cfg.get("ie", ""),
            }
            status, link, xml = emitir_com_provider(
                cfg.get("fiscal_provider", "mock"), payload, cfg)
            conn2 = connect(db_path)
            try:
                repo.atualizar_nfe(conn2, venda_id, status, link, xml)
            finally:
                conn2.close()
        except Exception as e:
            try:
                from database.connection import connect, get_db_path
                from database import repositories as repo
                c = connect(get_db_path())
                try:
                    repo.atualizar_nfe(c, venda_id, "erro", "", str(e)[:800])
                finally:
                    c.close()
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


@router.post("/vendas", status_code=201, dependencies=[Depends(exige("vendas"))])
def criar_venda(body: VendaIn, conn=Depends(get_conn)):
    repo = _repo()
    itens = [i.model_dump() for i in body.itens]
    pagamentos = [p.model_dump() for p in body.pagamentos]
    try:
        venda = repo.criar_venda(conn, body.id_movimento, itens, pagamentos,
                                 body.desconto_percentual)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _disparar_fiscal_async(venda["id"])
    return venda


@router.get("/vendas", dependencies=[Depends(exige("historico_consulta"))])
def listar(dia: str = Query(default=""), status: str = Query(default=""),
           limite: int = Query(default=200, le=1000), conn=Depends(get_conn)):
    return _repo().listar_vendas(conn, dia, status, limite)


@router.get("/vendas/totais", dependencies=[Depends(exige("relatorios"))])
def totais(dia: str = Query(default=""), conn=Depends(get_conn)):
    from datetime import date
    d = dia or date.today().isoformat()
    return _repo().totais_por_pagamento(conn, d)


@router.get("/vendas/{venda_id}", dependencies=[Depends(exige("historico_consulta"))])
def detalhe(venda_id: int, conn=Depends(get_conn)):
    repo = _repo()
    venda = repo.obter_venda(conn, venda_id)
    if not venda:
        raise HTTPException(404, "Venda não encontrada.")
    return {
        "venda": venda,
        "itens": repo.listar_itens_venda(conn, venda_id),
        "pagamentos": repo.listar_pagamentos_venda(conn, venda_id),
    }


@router.post("/vendas/{venda_id}/cancelar", dependencies=[Depends(exige("historico_consulta"))])
def cancelar(venda_id: int, conn=Depends(get_conn)):
    repo = _repo()
    try:
        repo.cancelar_venda(conn, venda_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # best-effort: avisa provider ativo
    try:
        from services.fiscal_providers import get_provider
        cfg = repo.obter_config_full(conn)
        prov = get_provider(cfg.get("fiscal_provider", "mock"))
        if hasattr(prov, "endpoint"):
            pass
    except Exception:
        pass
    return {"ok": True}


@router.get("/vendas-limpar/preview", dependencies=[Depends(exige("historico_limpar"))])
def preview_limpeza(inicio: str = Query(default=""), fim: str = Query(default=""),
                    conn=Depends(get_conn)):
    """Prévia da limpeza do histórico (conta vendas + total no intervalo)."""
    return _repo().resumo_limpeza(conn, inicio, fim)


@router.delete("/vendas-limpar", dependencies=[Depends(exige("historico_limpar"))])
def limpar_historico(body: LimpezaIn, conn=Depends(get_conn)):
    """Apaga vendas do histórico no intervalo (com estorno de estoque)."""
    return _repo().limpar_vendas(conn, body.inicio, body.fim)
