"""Geração de arquivos de teste fiscal/impressão (txt + pdf).

- Teste Mock -> emite nota de exemplo no mock-sefaz e salva espelho/cupom/xml/pdf
  em data/notas_teste/ para conferência e impressão futura.
- Teste impressão -> monta cupom de exemplo e salva em data/cupons/.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def notas_dir() -> Path:
    d = _base_dir() / "data" / "notas_teste"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cupons_dir() -> Path:
    d = _base_dir() / "data" / "cupons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def salvar_texto(pasta: Path, nome: str, conteudo: str) -> Path:
    p = pasta / nome
    p.write_text(conteudo or "", encoding="utf-8")
    return p


def exemplo_payload() -> dict:
    return {
        "venda_id": 999,
        "total": 15.0,
        "uf": "MG",
        "regime_tributario": "simples",
        "com_st": True,
        "cliente": {"nome": "Consumidor Final (teste)"},
        "itens": [
            {"descricao": "Picole Chocolate (teste)", "quantidade": 2,
             "valor_unitario": 5.0, "ncm": "21050010"},
            {"descricao": "Cascao Baunilha (teste)", "quantidade": 1,
             "valor_unitario": 5.0, "ncm": "21050090"},
        ],
        "pagamentos": [{"forma": "pix", "valor": 15.0}],
    }


def emitir_mock_teste_e_salvar(cfg: dict) -> dict:
    """POST no mock, salva espelho.txt + cupom.txt + .xml + .pdf. Retorna resumo."""
    import requests

    base = (cfg.get("mock_url") or "http://localhost:3000").rstrip("/")
    url = f"{base}/v1/notas"
    payload = exemplo_payload()
    try:
        resp = requests.post(url, json=payload, timeout=20)
    except Exception as e:
        raise RuntimeError(f"Mock inalcançável em {url}: {e}")
    if not (200 <= getattr(resp, "status_code", 0) < 300):
        raise RuntimeError(f"Mock recusou (HTTP {getattr(resp, 'status_code', '?')}): {resp.text[:500]}")
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError("Mock retornou resposta não-JSON.")
    ts = _ts()
    id_nota = str(data.get("id_nota") or f"nota_teste_{ts}")
    espelho = str(data.get("espelho_txt") or "")
    cupom = str(data.get("cupom_48col") or "")
    xml = str(data.get("xml") or "")
    arquivos: list[str] = []
    if espelho:
        p = salvar_texto(notas_dir(), f"{id_nota}_espelho.txt", espelho)
        arquivos.append(p.name)
    if cupom:
        p = salvar_texto(notas_dir(), f"{id_nota}_cupom48.txt", cupom)
        arquivos.append(p.name)
    if xml:
        p = salvar_texto(notas_dir(), f"{id_nota}.xml", xml)
        arquivos.append(p.name)
    # baixa o DANFE pdf do mock
    pdf_nome = ""
    try:
        rpdf = requests.get(f"{base}/v1/notas/{id_nota}/danfe.pdf", timeout=20)
        if getattr(rpdf, "status_code", 0) == 200 and rpdf.content[:4] == b"%PDF":
            ppdf = notas_dir() / f"{id_nota}_danfe.pdf"
            ppdf.write_bytes(rpdf.content)
            arquivos.append(ppdf.name)
            pdf_nome = ppdf.name
    except Exception:
        pass
    return {
        "ok": True,
        "id_nota": id_nota,
        "chave_acesso": str(data.get("chave_acesso") or ""),
        "protocolo": str(data.get("protocolo") or ""),
        "arquivos": arquivos,
        "pdf": pdf_nome,
        "espelho_preview": espelho[:2000],
        "cupom_preview": cupom[:1200],
    }


def gerar_cupom_teste_e_salvar(cfg: dict | None = None) -> dict:
    """Monta o comprovante de exemplo (modelo salvo em Configurações) e salva o txt."""
    import sys
    SRC = Path(__file__).resolve().parents[1]
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    try:
        from services.impressao import montar_cupom
    except ImportError:
        from src.services.impressao import montar_cupom
    venda = {"id": 999, "total": 31.39, "desconto_percentual": 0,
             "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    itens = [
        {"nome": "Produto de exemplo 500g", "quantidade": 2,
         "valor_unitario": 12.50, "subtotal": 25.00},
        {"nome": "Bebida exemplo 1L", "quantidade": 1,
         "valor_unitario": 6.39, "subtotal": 6.39},
    ]
    pagamentos = [{"metodo": "debito", "valor": 31.39, "parcelas": 1}]
    texto = montar_cupom(venda, itens, pagamentos, cfg or {},
                         "http://exemplo.local/nfce/123", troco=0.0)
    ts = _ts()
    p = salvar_texto(cupons_dir(), f"teste_impressao_{ts}.txt", texto)
    return {"ok": True, "arquivo": p.name, "preview": texto[:1500]}
