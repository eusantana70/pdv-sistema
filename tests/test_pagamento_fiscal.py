"""M5 (split) e M6 (fiscal/impressão). Venv: python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from database.connection import connect  # noqa: E402
from database.schema import init_db  # noqa: E402
from database import repositories as repo  # noqa: E402
from services.pagamentos import SplitPagamento  # noqa: E402
from services.fiscal import tentar_emitir  # noqa: E402
from services.fiscal_payload import montar_payload_nfce  # noqa: E402
from services.impressao import montar_cupom  # noqa: E402


class FakeResp:
    def __init__(self, code, data):
        self.status_code = code
        self._data = data

    def json(self):
        return self._data


class TestSplitM5(unittest.TestCase):
    def test_split_50_15pix_35(self):
        s = SplitPagamento(total=50.0)
        self.assertEqual(s.adicionar("pix", 15.0), 35.0)
        self.assertFalse(s.concluido())
        self.assertEqual(s.adicionar("debito", 35.0), 0.0)
        self.assertTrue(s.concluido())

    def test_troco_so_dinheiro_conceito(self):
        s = SplitPagamento(total=50.0)
        s.adicionar("dinheiro", 60.0)
        self.assertEqual(s.troco(), 10.0)
        self.assertTrue(s.concluido())

    def test_credito_parcelas(self):
        s = SplitPagamento(total=100.0)
        s.adicionar("credito", 100.0, parcelas=12)
        self.assertEqual(s.partes[0].parcelas, 12)
        with self.assertRaises(ValueError):
            SplitPagamento(total=100.0).adicionar("credito", 100.0, parcelas=13)


class TestFiscalM6(unittest.TestCase):
    def test_emitir_ok(self):
        st, link, xml = tentar_emitir(
            {"venda_id": 1}, "tok", "http://fiscal/nfce",
            post=lambda *a, **k: FakeResp(200, {"link": "http://pdf/1", "xml": "<xml/>"}))
        self.assertEqual((st, link, xml), ("autorizado", "http://pdf/1", "<xml/>"))

    def test_emitir_erro_nao_bloqueia(self):
        st, link, xml = tentar_emitir(
            {"venda_id": 1}, "tok", "http://fiscal/nfce",
            post=lambda *a, **k: FakeResp(500, {"message": "SEFAZ fora"}))
        self.assertEqual(st, "erro")
        self.assertIn("SEFAZ", xml)

    def test_sem_url_pendente(self):
        self.assertEqual(tentar_emitir({}, "", "")[0], "pendente")

    def test_payload_tem_perfil(self):
        venda = {"id": 7, "total": 15.0, "data_hora": "2026-01-01T10:00:00"}
        itens = [{"id_produto": 1, "nome": "Picole", "quantidade": 3,
                  "valor_unitario": 5.0, "subtotal": 15.0, "id_perfil_fiscal": 9}]
        pays = [{"metodo": "pix", "valor": 15.0}]
        perfis = {9: {"ncm": "21050010", "cfop": "5102"}}
        p = montar_payload_nfce(venda, itens, pays, perfis)
        self.assertEqual(p["itens"][0]["perfil_fiscal"]["cfop"], "5102")

    def test_cupom_contem_total_e_link(self):
        venda = {"id": 3, "total": 42.5, "data_hora": "x"}
        itens = [{"nome": "Picole", "quantidade": 2, "valor_unitario": 5.0, "subtotal": 10.0}]
        txt = montar_cupom(venda, itens, [{"metodo": "pix", "valor": 42.5}],
                           "Termica", "http://qr/3")
        self.assertIn("42.50", txt)
        self.assertIn("http://qr/3", txt)

    def test_venda_split_multipagamentos(self):
        tf = tempfile.mktemp(suffix=".db")
        init_db(tf)
        conn = connect(tf)
        try:
            pid = repo.criar_perfil(conn, "P", "21050010", "5102", "102", "0")
            p = repo.criar_produto(conn, "Picole", 50.0, 10, pid)
            m = repo.abrir_caixa(conn, 0)
            venda = repo.criar_venda(
                conn, m["id"], [{"id_produto": p["id"], "quantidade": 1}],
                [{"metodo": "pix", "valor": 15.0},
                 {"metodo": "dinheiro", "valor": 35.0}])
            self.assertAlmostEqual(venda["total"], 50.0)
            pays = repo.listar_pagamentos_venda(conn, venda["id"])
            self.assertEqual(len(pays), 2)
            self.assertEqual(venda["nfe_status"], "pendente")
        finally:
            conn.close()
            for suf in ("", "-wal", "-shm"):
                try:
                    os.remove(tf + suf)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
