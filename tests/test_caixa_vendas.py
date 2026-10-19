"""M3 (caixa) e M4 (vendas/carrinho). Rodar: venv python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from database.connection import connect  # noqa: E402
from database.schema import init_db  # noqa: E402
from database import repositories as repo  # noqa: E402
from services.carrinho import Carrinho  # noqa: E402


def _seed_prod(conn, nome="Picole", preco=5.0, estoque=10):
    pid = repo.criar_perfil(conn, "P", "21050010", "5102", "102", "0")
    return repo.criar_produto(conn, nome, preco, estoque, pid)


class TestCaixa(unittest.TestCase):
    def setUp(self):
        self.tf = tempfile.mktemp(suffix=".db")
        init_db(self.tf)
        self.conn = connect(self.tf)

    def tearDown(self):
        self.conn.close()
        for suf in ("", "-wal", "-shm"):
            try:
                os.remove(self.tf + suf)
            except OSError:
                pass

    def test_abrir_so_um(self):
        m1 = repo.abrir_caixa(self.conn, 100)
        self.assertEqual(m1["status"], "aberto")
        with self.assertRaises(ValueError):
            repo.abrir_caixa(self.conn, 50)
        repo.fechar_caixa(self.conn, m1["id"], 120)
        m2 = repo.abrir_caixa(self.conn, 0)
        self.assertIsNotNone(repo.obter_caixa_aberto(self.conn))
        self.assertEqual(m2["valor_inicial"], 0)

    def test_sangria_suprimento_e_saldo(self):
        m = repo.abrir_caixa(self.conn, 100)
        repo.adicionar_operacao(self.conn, m["id"], "suprimento", 50, "troco")
        repo.adicionar_operacao(self.conn, m["id"], "sangria", 30, "")
        self.assertAlmostEqual(repo.saldo_previsto_caixa(self.conn, m["id"]), 120.0)
        with self.assertRaises(ValueError):
            repo.adicionar_operacao(self.conn, m["id"], "sangria", 0)

    def test_operacao_exige_caixa_aberto(self):
        m = repo.abrir_caixa(self.conn, 0)
        repo.fechar_caixa(self.conn, m["id"], 0)
        with self.assertRaises(ValueError):
            repo.adicionar_operacao(self.conn, m["id"], "sangria", 10)


class TestVendas(unittest.TestCase):
    def setUp(self):
        self.tf = tempfile.mktemp(suffix=".db")
        init_db(self.tf)
        self.conn = connect(self.tf)

    def tearDown(self):
        self.conn.close()
        for suf in ("", "-wal", "-shm"):
            try:
                os.remove(self.tf + suf)
            except OSError:
                pass

    def test_venda_deduz_estoque(self):
        m = repo.abrir_caixa(self.conn, 0)
        p = _seed_prod(self.conn, estoque=10)
        venda = repo.criar_venda(
            self.conn, m["id"],
            [{"id_produto": p["id"], "quantidade": 3}],
            [{"metodo": "dinheiro", "valor": 15.0}])
        self.assertAlmostEqual(venda["total"], 15.0)
        prod = repo.obter_produto(self.conn, p["id"])
        self.assertAlmostEqual(float(prod["quantidade_estoque"]), 7.0)

    def test_venda_sem_valor_unitario_usa_preco_cadastrado(self):
        """A tela manda o item sem valor_unitario (a chave chega como None,
        nao ausente). Sem tratar esse None, toda venda quebrava com 500."""
        m = repo.abrir_caixa(self.conn, 0)
        p = _seed_prod(self.conn, preco=7.5, estoque=10)
        venda = repo.criar_venda(
            self.conn, m["id"],
            [{"id_produto": p["id"], "quantidade": 2, "valor_unitario": None}],
            [{"metodo": "pix", "valor": 15.0}])
        self.assertAlmostEqual(venda["total"], 15.0)
        itens = repo.listar_itens_venda(self.conn, venda["id"])
        self.assertAlmostEqual(float(itens[0]["valor_unitario"]), 7.5)

    def test_venda_aceita_valor_unitario_editado(self):
        m = repo.abrir_caixa(self.conn, 0)
        p = _seed_prod(self.conn, preco=7.5, estoque=10)
        venda = repo.criar_venda(
            self.conn, m["id"],
            [{"id_produto": p["id"], "quantidade": 2, "valor_unitario": 5.0}],
            [{"metodo": "pix", "valor": 10.0}])
        self.assertAlmostEqual(venda["total"], 10.0)

    def test_venda_caixa_fechado_bloqueia(self):
        p = _seed_prod(self.conn)
        m = repo.abrir_caixa(self.conn, 0)
        repo.fechar_caixa(self.conn, m["id"], 0)
        with self.assertRaises(ValueError):
            repo.criar_venda(self.conn, m["id"],
                             [{"id_produto": p["id"], "quantidade": 1}],
                             [{"metodo": "pix", "valor": 5.0}])

    def test_venda_sem_estoque_bloqueia(self):
        m = repo.abrir_caixa(self.conn, 0)
        p = _seed_prod(self.conn, estoque=1)
        with self.assertRaises(ValueError):
            repo.criar_venda(self.conn, m["id"],
                             [{"id_produto": p["id"], "quantidade": 5}],
                             [{"metodo": "pix", "valor": 25.0}])

    def test_venda_pagamento_insuficiente(self):
        m = repo.abrir_caixa(self.conn, 0)
        p = _seed_prod(self.conn, preco=10)
        with self.assertRaises(ValueError):
            repo.criar_venda(self.conn, m["id"],
                             [{"id_produto": p["id"], "quantidade": 1}],
                             [{"metodo": "pix", "valor": 5.0}])


class TestCarrinho(unittest.TestCase):
    def test_agrupa_e_total(self):
        c = Carrinho()
        prod = {"id": 1, "nome": "Picole", "codigo_interno": "1234",
                "preco_venda": 5.0, "quantidade_estoque": 10}
        c.adicionar(prod, 2)
        c.adicionar(prod, 1)
        self.assertEqual(len(c.itens), 1)
        self.assertAlmostEqual(c.total(), 15.0)

    def test_estouro_estoque(self):
        c = Carrinho()
        prod = {"id": 1, "nome": "Picole", "codigo_interno": "1234",
                "preco_venda": 5.0, "quantidade_estoque": 2}
        c.adicionar(prod, 2)
        with self.assertRaises(ValueError):
            c.adicionar(prod, 1)


if __name__ == "__main__":
    unittest.main()
