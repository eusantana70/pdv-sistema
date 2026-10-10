"""Monta o payload JSON da NFC-e para envio assíncrono (Módulo 6).

Não faz a chamada HTTP aqui — o worker fiscal (services/fiscal.py, futuro)
vai ler este payload e fazer POST em background para api_nfce_url.
"""

from __future__ import annotations


def montar_payload_nfce(venda: dict, itens: list, pagamentos: list, perfis: dict) -> dict:
    return {
        "venda_id": venda.get("id"),
        "total": venda.get("total"),
        "data_hora": venda.get("data_hora"),
        "itens": [
            {
                "produto_id": i.get("id_produto"),
                "descricao": i.get("nome", ""),
                "quantidade": i.get("quantidade"),
                "valor_unitario": i.get("valor_unitario"),
                "subtotal": i.get("subtotal"),
                "perfil_fiscal": perfis.get(i.get("id_perfil_fiscal"), {}),
            }
            for i in itens
        ],
        "pagamentos": pagamentos,
    }
