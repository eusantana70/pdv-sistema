"""Fiscal: status da nota, reemissão manual, cupom e arquivos de teste."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import base64

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response

from .auth import exige, usuario_atual
from .deps import get_conn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


@router.get("/fiscal/nota/{venda_id}", dependencies=[Depends(exige("vendas"))])
def status_nota(venda_id: int, conn=Depends(get_conn)):
    repo = _repo()
    venda = repo.obter_venda(conn, venda_id)
    if not venda:
        raise HTTPException(404, "Venda não encontrada.")
    return {
        "venda_id": venda_id,
        "nfe_status": venda.get("nfe_status", "pendente"),
        "link": venda.get("nfe_link_cupom", ""),
        "xml": venda.get("nfe_xml", ""),
    }


@router.post("/fiscal/emitir/{venda_id}", dependencies=[Depends(exige("vendas"))])
def reemitir(venda_id: int, conn=Depends(get_conn)):
    repo = _repo()
    venda = repo.obter_venda(conn, venda_id)
    if not venda:
        raise HTTPException(404, "Venda não encontrada.")
    itens = repo.listar_itens_venda(conn, venda_id)
    pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
    perfis = {p["id"]: p for p in repo.listar_perfis(conn)}
    cfg = repo.obter_config_full(conn)
    try:
        from services.fiscal_payload import montar_payload_nfce
        from services.fiscal_providers import emitir_com_provider
    except ImportError:
        from src.services.fiscal_payload import montar_payload_nfce
        from src.services.fiscal_providers import emitir_com_provider
    payload = montar_payload_nfce(venda, itens, pagamentos, perfis)
    payload["ambiente"] = cfg.get("ambiente", "homologacao")
    payload["modelo"] = cfg.get("modelo_doc", "NFC-e")
    payload["serie"] = cfg.get("serie", "1")
    status, link, xml = emitir_com_provider(cfg.get("fiscal_provider", "mock"), payload, cfg)
    repo.atualizar_nfe(conn, venda_id, status, link, xml)
    return {"venda_id": venda_id, "nfe_status": status, "link": link, "xml": xml}


@router.get("/fiscal/cupom/{venda_id}", response_class=PlainTextResponse, dependencies=[Depends(exige("vendas"))])
def cupom(venda_id: int, conn=Depends(get_conn)):
    repo = _repo()
    venda = repo.obter_venda(conn, venda_id)
    if not venda:
        raise HTTPException(404, "Venda não encontrada.")
    itens = repo.listar_itens_venda(conn, venda_id)
    pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
    cfg = repo.obter_config_full(conn)
    troco = float(venda.get("troco") or 0) or None
    try:
        from services.impressao import montar_cupom
    except ImportError:
        from src.services.impressao import montar_cupom
    return montar_cupom(venda, itens, pagamentos, cfg,
                        venda.get("nfe_link_cupom", ""), troco=troco)


@router.get("/fiscal/qrcode", dependencies=[Depends(exige("configuracoes"))])
def qrcode_recibo(link: str = "", conn=Depends(get_conn)):
    """QR Code do comprovante (link salvo ou informado na tela).

    Devolve a imagem embutida (data URI) porque <img src> não leva o token
    de autenticação — assim a prévia funciona dentro do app logado.
    """
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    alvo = (link or cfg.get("recibo_qrcode_link") or "").strip()
    if not alvo.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Informe um link começando com http:// ou https://")
    try:
        from services.impressao import qr_svg
        from services import impressao as _impressao
    except ImportError:
        from src.services.impressao import qr_svg
        from src.services import impressao as _impressao
    svg = qr_svg(alvo)
    if not svg:
        raise HTTPException(
            500,
            "QR Code indisponível: instale uma das bibliotecas "
            "(pip install qrcode  ou  pip install segno).")
    dados = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"data_uri": f"data:image/svg+xml;base64,{dados}",
            "link": alvo,
            "biblioteca": _impressao.LIBERACAO_QR}


@router.get("/fiscal/recibo-preview", dependencies=[Depends(exige("configuracoes"))])
def recibo_preview(conn=Depends(get_conn)):
    """Prévia do modelo da nota NÃO fiscal com os dados salvos na configuração."""
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    try:
        from services.impressao import montar_cupom, LARG_PADRAO
    except ImportError:
        from src.services.impressao import montar_cupom, LARG_PADRAO
    venda = {
        "id": 999,
        "total": 31.39,
        "desconto_percentual": 0,
        "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    itens = [
        {"nome": "Produto de exemplo 500g", "quantidade": 2, "valor_unitario": 12.50, "subtotal": 25.00},
        {"nome": "Bebida exemplo 1L", "quantidade": 1, "valor_unitario": 6.39, "subtotal": 6.39},
    ]
    pagamentos = [
        {"metodo": "debito", "valor": 31.39, "parcelas": 1},
    ]
    texto = montar_cupom(venda, itens, pagamentos, cfg,
                         "http://exemplo.local/nfce/123", troco=0.0, atendente="Operador")
    larg = LARG_PADRAO
    try:
        larg = int(str(cfg.get("recibo_largura") or LARG_PADRAO))
    except (TypeError, ValueError):
        pass
    return {"texto": texto, "largura": larg}


@router.post("/fiscal/teste-mock", dependencies=[Depends(exige("configuracoes"))])
def teste_mock(conn=Depends(get_conn)):
    """Emite nota de TESTE no mock e salva espelho/cupom/xml/pdf em data/notas_teste/."""
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    try:
        from services.arquivos_fiscais import emitir_mock_teste_e_salvar
    except ImportError:
        from src.services.arquivos_fiscais import emitir_mock_teste_e_salvar
    try:
        return emitir_mock_teste_e_salvar(cfg)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/fiscal/teste-impressao", dependencies=[Depends(exige("configuracoes"))])
def teste_impressao(conn=Depends(get_conn)):
    """Gera cupom de TESTE e salva txt em data/cupons/ (vale até ter impressora)."""
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    try:
        from services.arquivos_fiscais import gerar_cupom_teste_e_salvar
    except ImportError:
        from src.services.arquivos_fiscais import gerar_cupom_teste_e_salvar
    return gerar_cupom_teste_e_salvar(cfg)


@router.post("/fiscal/imprimir/{venda_id}")
def imprimir_documento(venda_id: int, tipo: str = "nao_fiscal",
                      request: Request = None, conn=Depends(get_conn)):
    """Imprime a venda. Sem impressora disponível, salva o documento em PDF.

    tipo: "nao_fiscal" (comprovante) ou "fiscal" (nota fiscal).
    Devolve o modo usado ("impresso" ou "pdf") e o arquivo gerado.
    """
    if tipo not in ("fiscal", "nao_fiscal"):
        raise HTTPException(400, "tipo deve ser fiscal ou nao_fiscal.")
    repo = _repo()
    u = usuario_atual(request)
    if not u:
        raise HTTPException(401, "Faça login para imprimir documentos.")
    # permissão: vendas para o comprovante, configuracoes para a nota fiscal
    chave = "configuracoes" if tipo == "fiscal" else "vendas"
    try:
        from services import permissoes as P
    except ImportError:
        from src.services import permissoes as P
    if not P.pode(u.get("perfil", "operador"), chave):
        raise HTTPException(403, "Seu perfil não tem acesso a esta função.")
    venda = repo.obter_venda(conn, venda_id)
    if not venda:
        raise HTTPException(404, "Venda não encontrada.")
    itens = repo.listar_itens_venda(conn, venda_id)
    pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
    cfg = repo.obter_config_full(conn)
    try:
        from services.impressao import (
            imprimir_texto_windows, montar_cupom, linhas_nota_fiscal,
            salvar_pdf_fiscal, salvar_pdf_recibo,
        )
    except ImportError:
        from src.services.impressao import (
            imprimir_texto_windows, montar_cupom, linhas_nota_fiscal,
            salvar_pdf_fiscal, salvar_pdf_recibo,
        )
    impressora = str(cfg.get("impressora_nome") or "")
    if tipo == "fiscal":
        texto = "\n".join(linhas_nota_fiscal(venda, itens, pagamentos, cfg))
        salvar = lambda: salvar_pdf_fiscal(venda, itens, pagamentos, cfg)  # noqa: E731
        nome = "Nota fiscal"
    else:
        texto = montar_cupom(venda, itens, pagamentos, cfg, venda.get("nfe_link_cupom", ""))
        salvar = lambda: salvar_pdf_recibo(venda, itens, pagamentos, cfg)  # noqa: E731
        nome = "Comprovante"

    ok, msg = imprimir_texto_windows(texto, impressora)
    if ok:
        return {"ok": True, "modo": "impresso", "tipo": tipo, "mensagem": msg}
    caminho = salvar()
    arquivo = Path(caminho).name
    pasta = "notas" if tipo == "fiscal" else "cupons"
    return {
        "ok": True,
        "modo": "pdf",
        "tipo": tipo,
        "arquivo": arquivo,
        "pasta": pasta,
        "url": f"/api/fiscal/arquivo/{pasta}/{arquivo}",
        "mensagem": f"{msg} {nome} salvo em PDF ({pasta}/{arquivo}).",
    }


@router.get("/fiscal/arquivo/{pasta}/{nome}", dependencies=[Depends(exige("configuracoes"))])
def baixar_arquivo(pasta: str, nome: str):
    """Download dos arquivos gerados (pastas: notas_teste, cupons, notas)."""
    if pasta not in ("notas_teste", "cupons", "notas"):
        raise HTTPException(400, "Pasta inválida.")
    if not nome or "/" in nome or "\\" in nome or ".." in nome:
        raise HTTPException(400, "Nome inválido.")
    base = Path(__file__).resolve().parents[2] / "data" / pasta / nome
    if not base.exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    media = "application/pdf" if nome.lower().endswith(".pdf") else "text/plain; charset=utf-8"
    return FileResponse(str(base), media_type=media, filename=nome)
