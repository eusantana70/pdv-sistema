"""Relatórios diário/semanal/mensal para a faixa do front."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from .auth import exige
from .deps import get_conn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


def _range(periodo: str, ref: str) -> list[str]:
    base = date.fromisoformat(ref) if ref else date.today()
    if periodo == "diario":
        return [base.isoformat()]
    if periodo == "semanal":
        return [(base - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    # mensal: últimos 30 dias
    return [(base - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

def _lista(valor: str) -> list[str]:
    return [v.strip() for v in (valor or "").split(",") if v.strip()]


@router.get("/relatorios/dados", dependencies=[Depends(exige("relatorios"))])
def dados_relatorio(periodo: str = Query(default="mensal"),
                    data: str = Query(default=""),
                    inicio: str = Query(default=""),
                    fim: str = Query(default=""),
                    formas: str = Query(default=""),
                    categorias: str = Query(default=""),
                    produtos: str = Query(default=""),
                    agrupar: str = Query(default="dia"),
                    conn=Depends(get_conn)):
    """Dataset do relatório com filtros (data, forma de pagamento, produto/categoria)."""
    if agrupar not in ("dia", "hora"):
        agrupar = "dia"
    if periodo not in ("diario", "semanal", "mensal", "personalizado"):
        periodo = "mensal"
    dias = _range("mensal" if periodo == "personalizado" else periodo, data)
    ini, f = (inicio, fim) if (inicio or fim) else (dias[0], dias[-1])
    repo = _repo()
    return repo.relatorio_detalhado(conn, ini, f,
                                    formas=_lista(formas),
                                    categorias=_lista(categorias),
                                    produtos=_lista(produtos),
                                    agrupar=agrupar)


@router.post("/relatorios/gerar-pdf", dependencies=[Depends(exige("relatorios"))])
def gerar_pdf_relatorio(body: dict, conn=Depends(get_conn)):
    """Gera o relatório completo em PDF (com ou sem gráficos) e salva em data/relatorios/."""
    from datetime import datetime
    from pathlib import Path
    repo = _repo()
    periodo = str(body.get("periodo") or "mensal")
    dias = _range("mensal" if periodo == "personalizado" else periodo,
                  str(body.get("data") or ""))
    ini = str(body.get("inicio") or dias[0])
    f = str(body.get("fim") or dias[-1])
    dados = repo.relatorio_detalhado(
        conn, ini, f,
        formas=[str(x) for x in (body.get("formas") or [])],
        categorias=[str(x) for x in (body.get("categorias") or [])],
        produtos=[str(x) for x in (body.get("produtos") or [])],
        agrupar=str(body.get("agrupar") or "dia"))
    cfg = repo.obter_config_full(conn)
    opcoes = {
        "grafico_linhas": bool(body.get("grafico_linhas", True)),
        "grafico_pizza": bool(body.get("grafico_pizza", True)),
        "grafico_barras": bool(body.get("grafico_barras", False)),
        "campo_linhas": str(body.get("campo_linhas") or "total"),
        "fatia_pizza": str(body.get("fatia_pizza") or "forma"),
        "paisagem": bool(body.get("paisagem", False)),
    }
    try:
        from services.relatorio_pdf import gerar_relatorio_pdf
    except ImportError:
        from src.services.relatorio_pdf import gerar_relatorio_pdf
    pdf = gerar_relatorio_pdf(dados, cfg, opcoes)

    pasta = Path(__file__).resolve().parents[2] / "data" / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    nome = f"relatorio_{carimbo}.pdf"
    destino = pasta / nome
    destino.write_bytes(pdf)
    return {
        "ok": True, "arquivo": nome, "url": f"/api/relatorios/arquivo/{nome}",
        "bytes": len(pdf), "graficos": {k: v for k, v in opcoes.items() if k.startswith("grafico")},
        "resumo": dados["resumo"],
    }


@router.get("/relatorios/arquivo/{nome}", dependencies=[Depends(exige("relatorios"))])
def baixar_relatorio(nome: str):
    """Download do relatório em PDF gerado."""
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    if not nome or "/" in nome or "\\" in nome or ".." in nome:
        raise HTTPException(400, "Nome inválido.")
    base = Path(__file__).resolve().parents[2] / "data" / "relatorios" / nome
    if not base.exists():
        raise HTTPException(404, "Relatório não encontrado.")
    return FileResponse(str(base), media_type="application/pdf", filename=nome)

@router.get("/relatorios/{periodo}", dependencies=[Depends(exige("relatorios"))])
def relatorio(periodo: str, data: str = Query(default=""), conn=Depends(get_conn)):
    if periodo not in ("diario", "semanal", "mensal"):
        from fastapi import HTTPException
        raise HTTPException(400, "periodo deve ser diario, semanal ou mensal.")
    repo = _repo()
    dias = _range(periodo, data)
    serie = [{"dia": d, **repo.totais_por_pagamento(conn, d)} for d in dias]
    total = round(sum(s["_geral"] for s in serie), 2)
    vendas = sum(s["_vendas"] for s in serie)
    return {"periodo": periodo, "dias": serie, "total_geral": total, "vendas": vendas}

