"""Config completa + fiscal multi-provedor (a parte das notas pedida)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .auth import exige
from .deps import get_conn
from .schemas import ConfigIn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


@router.get("/config")
def obter(conn=Depends(get_conn)):
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    try:
        from services.fiscal_providers import PROVIDER_CHOICES
    except ImportError:
        from src.services.fiscal_providers import PROVIDER_CHOICES
    return {**cfg, "providers_disponiveis": PROVIDER_CHOICES}


@router.put("/config", dependencies=[Depends(exige("configuracoes"))])
def salvar(body: ConfigIn, conn=Depends(get_conn)):
    repo = _repo()
    dados = {k: v for k, v in body.model_dump().items() if v is not None}
    if "fiscal_provider" in dados:
        validos = {"mock", "nuvem_fiscal", "focus_nfe", "sefaz_direta", "custom"}
        if dados["fiscal_provider"] not in validos:
            raise HTTPException(400, f"fiscal_provider inválido. Use: {sorted(validos)}")
    if "ambiente" in dados and dados["ambiente"] not in ("producao", "homologacao"):
        raise HTTPException(400, "ambiente deve ser producao ou homologacao.")
    if "desconto_tipo" in dados and dados["desconto_tipo"] not in ("nenhum", "percentual", "valor"):
        raise HTTPException(400, "desconto_tipo deve ser nenhum, percentual ou valor.")
    if "desconto_valor" in dados and float(dados["desconto_valor"] or 0) < 0:
        raise HTTPException(400, "desconto_valor deve ser >= 0.")
    if "recibo_largura" in dados and str(dados["recibo_largura"]) not in ("32", "48"):
        raise HTTPException(400, "recibo_largura deve ser 32 ou 48 (colunas).")
    if "recibo_qrcode_link" in dados and dados["recibo_qrcode_link"]:
        link = str(dados["recibo_qrcode_link"]).strip()
        if not link.lower().startswith(("http://", "https://")):
            raise HTTPException(400, "recibo_qrcode_link deve começar com http:// ou https://")
    for chave, rotulo in (("recibo_tributos_federal", "federal"),
                          ("recibo_tributos_estadual", "estadual")):
        if chave in dados and not (0 <= float(dados[chave] or 0) <= 100):
            raise HTTPException(400, f"Tributo {rotulo} deve estar entre 0 e 100 (%).")
    return repo.salvar_config_full(conn, dados)


@router.get("/config/fiscal/providers", dependencies=[Depends(exige("configuracoes"))])
def providers():
    try:
        from services.fiscal_providers import PROVIDER_CHOICES
    except ImportError:
        from src.services.fiscal_providers import PROVIDER_CHOICES
    return PROVIDER_CHOICES


@router.post("/config/fiscal/testar", dependencies=[Depends(exige("configuracoes"))])
def testar(body: dict | None = None, conn=Depends(get_conn)):
    """Testa a conexão do provider (usa config salva + overrides opcionais do body)."""
    repo = _repo()
    cfg = repo.obter_config_full(conn)
    if body:
        for k, v in body.items():
            if v is not None:
                cfg[k] = v
    provider_id = str((body or {}).get("fiscal_provider") or cfg.get("fiscal_provider", "mock"))
    try:
        from services.fiscal_providers import testar_provider
    except ImportError:
        from src.services.fiscal_providers import testar_provider
    ok, msg = testar_provider(provider_id, cfg)
    return {"ok": ok, "provider": provider_id, "mensagem": msg}
