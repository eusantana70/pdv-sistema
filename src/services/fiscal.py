"""Emissão NFC-e assíncrona (M6). Nunca bloqueia a venda.

Fluxo: PDV cria venda → FiscalThread (background) monta JSON (itens +
pagamentos + perfis fiscais) → POST na api_nfce_url com Bearer token →
atualiza vendas.nfe_status/link/xml como autorizado ou erro/pendente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def tentar_emitir(payload: dict, token: str, url: str,
                  post: Callable | None = None) -> tuple:
    """POST síncrono testável. Retorna (status, link, xml)."""
    import requests
    if not url:
        return ("pendente", "", "")
    fn = post or requests.post
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = fn(url, json=payload, headers=headers, timeout=20)
        status_code = getattr(resp, "status_code", 0)
        data = {}
        try:
            data = resp.json()
        except Exception:
            data = {}
        if 200 <= status_code < 300:
            link = str(data.get("link") or data.get("pdf") or data.get("cupom")
                       or data.get("qr") or data.get("url") or "")
            xml = str(data.get("xml") or "")
            return ("autorizado", link, xml)
        erro = str(data.get("message") or data.get("error") or data)[:500]
        return ("erro", "", erro)
    except Exception as e:
        return ("erro", "", str(e)[:500])


def montar_payload_da_venda(db_path, venda_id: int) -> tuple:
    """Lê banco e monta (payload, token, url)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from database.connection import connect
    from database import repositories as repo
    from services.fiscal_payload import montar_payload_nfce

    conn = connect(Path(db_path))
    try:
        venda = repo.obter_venda(conn, venda_id)
        if not venda:
            raise ValueError("Venda não encontrada.")
        itens = repo.listar_itens_venda(conn, venda_id)
        pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
        perfis = {p["id"]: p for p in repo.listar_perfis(conn)}
        cfg = repo.obter_config(conn)
    finally:
        conn.close()
    payload = montar_payload_nfce(venda, itens, pagamentos, perfis)
    return payload, cfg.get("api_nfce_token", ""), cfg.get("api_nfce_url", "")


try:
    from PySide6.QtCore import QThread, Signal

    class FiscalThread(QThread):
        """Thread Qt: emite NFC-e e grava resultado. Sinais: ok(int), falha(int, str)."""

        ok = Signal(int)
        falha = Signal(int, str)

        def __init__(self, db_path, venda_id: int, parent=None):
            super().__init__(parent)
            self.db_path = Path(db_path)
            self.venda_id = venda_id

        def run(self):  # noqa: D102
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            try:
                payload, token, url = montar_payload_da_venda(self.db_path, self.venda_id)
                status, link, xml = tentar_emitir(payload, token, url)
                from database.connection import connect
                from database import repositories as repo
                conn = connect(self.db_path)
                try:
                    repo.atualizar_nfe(conn, self.venda_id, status, link, xml)
                finally:
                    conn.close()
                if status == "autorizado":
                    self.ok.emit(self.venda_id)
                else:
                    self.falha.emit(self.venda_id, status)
            except Exception as e:
                try:
                    from database.connection import connect
                    from database import repositories as repo
                    conn = connect(self.db_path)
                    try:
                        repo.atualizar_nfe(conn, self.venda_id, "erro", "", str(e)[:500])
                    finally:
                        conn.close()
                except Exception:
                    pass
                self.falha.emit(self.venda_id, str(e)[:200])

except ImportError:  # PySide6 ausente (testes stdlib)
    FiscalThread = None  # type: ignore
