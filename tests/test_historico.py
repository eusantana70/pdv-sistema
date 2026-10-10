"""M7 (histórico/relatórios). Venv: python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from database.connection import connect  # noqa: E402
from database.schema import init_db  # noqa: E402
from database import repositories as repo  # noqa: E402


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self.tf = tempfile.mktemp(suffix=".db")
        init_db(self.tf)
        self.conn = connect(self.tf)
        self.pid = repo.criar_perfil(self.conn, "P", "21050010", "5102", "102", "0")
        self.prod = repo.criar_produto(self.conn, "Picole", 10.0, 20, self.pid)
        self.mov = repo.abrir_caixa(self.conn, 0)

    def tearDown(self):
        self.conn.close()
        for suf in ("", "-wal", "-shm"):
            try:
                os.remove(self.tf + suf)
            except OSError:
                pass

    def _vender(self, qtd=2, metodo="pix"):
        return repo.criar_venda(
            self.conn, self.mov["id"],
            [{"id_produto": self.prod["id"], "quantidade": qtd}],
            [{"metodo": metodo, "valor": 10.0 * qtd}])

    def test_cancelar_estorna_estoque(self):
        v = self._vender(qtd=2)
        self.assertAlmostEqual(float(repo.obter_produto(self.conn, self.prod["id"])["quantidade_estoque"]), 18.0)
        repo.cancelar_venda(self.conn, v["id"])
        self.assertEqual(repo.obter_venda(self.conn, v["id"])["status"], "cancelada")
        self.assertAlmostEqual(float(repo.obter_produto(self.conn, self.prod["id"])["quantidade_estoque"]), 20.0)
        with self.assertRaises(ValueError):
            repo.cancelar_venda(self.conn, v["id"])

    def test_totais_dia_por_pagamento(self):
        self._vender(qtd=1, metodo="dinheiro")   # 10
        self._vender(qtd=2, metodo="pix")        # 20
        self._vender(qtd=1, metodo="credito")    # 10
        v4 = self._vender(qtd=1, metodo="debito")  # 10 -> cancela
        repo.cancelar_venda(self.conn, v4["id"])
        hoje = datetime.now().strftime("%Y-%m-%d")
        tot = repo.totais_por_pagamento(self.conn, hoje)
        self.assertAlmostEqual(tot["dinheiro"], 10.0)
        self.assertAlmostEqual(tot["pix"], 20.0)
        self.assertAlmostEqual(tot["credito"], 10.0)
        self.assertAlmostEqual(tot["debito"], 0.0)  # cancelada não soma
        self.assertAlmostEqual(tot["_geral"], 40.0)
        self.assertEqual(tot["_vendas"], 3)

    def test_listar_filtra_dia_status(self):
        v = self._vender()
        hoje = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(len(repo.listar_vendas(self.conn, hoje, "")), 1)
        self.assertEqual(len(repo.listar_vendas(self.conn, hoje, "concluída")), 1)
        repo.cancelar_venda(self.conn, v["id"])
        self.assertEqual(len(repo.listar_vendas(self.conn, hoje, "concluída")), 0)
        self.assertEqual(len(repo.listar_vendas(self.conn, hoje, "cancelada")), 1)
        self.assertEqual(len(repo.listar_vendas(self.conn, "1999-01-01", "")), 0)


if __name__ == "__main__":
    unittest.main()
