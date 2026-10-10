"""Cupom + impressão térmica (M6). Win32 primeiro, ESC-POS como extensão futura."""

from __future__ import annotations

from pathlib import Path

LARG = 48


def _linha(char: str = "-") -> str:
    return char * LARG


def montar_cupom(venda: dict, itens: list, pagamentos: list,
                 impressora_nome: str = "", nfe_link: str = "") -> str:
    L = []
    L.append("PDV SORVETES".center(LARG))
    L.append("Cupom de venda - sem valor fiscal".center(LARG))
    L.append(_linha())
    L.append(f'Venda #{venda.get("id")}  {venda.get("data_hora", "")}')
    L.append(_linha())
    for it in itens:
        nome = str(it.get("nome") or f'Produto {it.get("id_produto")}')
        qtd = float(it.get("quantidade", 0))
        vu = float(it.get("valor_unitario", 0))
        sub = float(it.get("subtotal", 0))
        L.append(nome[:LARG])
        L.append(f"  {qtd:g} x R$ {vu:.2f} = R$ {sub:.2f}")
    L.append(_linha())
    L.append(f'TOTAL: R$ {float(venda.get("total", 0)):.2f}'.rjust(LARG))
    L.append("Pagamentos:")
    for p in pagamentos:
        extra = f' {p.get("parcelas")}x' if p.get("metodo") == "credito" else ""
        L.append(f'  {p.get("metodo")}{extra}: R$ {float(p.get("valor", 0)):.2f}')
    if nfe_link:
        L.append(_linha())
        L.append("NFC-e / QR Code:")
        L.append(nfe_link[:LARG])
    L.append(_linha())
    L.append("Obrigado pela preferencia!".center(LARG))
    if impressora_nome:
        L.append(f"Impressora: {impressora_nome}"[:LARG])
    L.append("\n\n")
    return "\n".join(L)


def imprimir_texto_windows(texto: str, impressora_nome: str) -> tuple:
    """Envia texto para a térmica via win32print. Retorna (ok, msg)."""
    if not impressora_nome:
        return (False, "Nenhuma impressora configurada (aba Configurações).")
    try:
        import win32print  # type: ignore
        import win32api  # type: ignore  # noqa: F401
    except ImportError:
        return (False, "pywin32 não instalado.")
    try:
        dados = texto.encode("cp850", errors="replace")
        h = win32print.OpenPrinter(impressora_nome)
        try:
            win32print.StartDocPrinter(h, 1, ("Cupom PDV", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, dados)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return (True, "Cupom enviado para a impressora.")
    except Exception as e:
        return (False, f"Falha ao imprimir: {e}")


def imprimir_cupom_venda(db_path, venda_id: int) -> tuple:
    """Carrega venda do banco, monta cupom e imprime. Retorna (ok, msg)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from database.connection import connect
    from database import repositories as repo

    conn = connect(Path(db_path))
    try:
        venda = repo.obter_venda(conn, venda_id)
        itens = repo.listar_itens_venda(conn, venda_id)
        pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
        cfg = repo.obter_config(conn)
    finally:
        conn.close()
    if not venda:
        return (False, "Venda não encontrada.")
    texto = montar_cupom(venda, itens, pagamentos,
                         cfg.get("impressora_nome", ""),
                         venda.get("nfe_link_cupom", ""))
    return imprimir_texto_windows(texto, cfg.get("impressora_nome", ""))
