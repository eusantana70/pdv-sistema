"""Teste stdlib (sem pytest): python -m unittest discover -s tests -v"""

import sqlite3
import unittest

from src.services.codigo_interno import gerar_codigo_interno
from src.services.pagamentos import SplitPagamento


class TestCodigoInterno(unittest.TestCase):
    def test_gera_4_digitos_unicos(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE produtos (codigo_interno TEXT UNIQUE)")
        vistos = {gerar_codigo_interno(conn) for _ in range(50)}
        self.assertEqual(len(vistos), 50)
        for c in vistos:
            self.assertRegex(c, r"^\d{4}$")


class TestSplit(unittest.TestCase):
    def test_split_50_15_pix_resta_35(self):
        s = SplitPagamento(total=50.0)
        self.assertEqual(s.adicionar("pix", 15.0), 35.0)
        self.assertFalse(s.concluido())
        self.assertEqual(s.adicionar("dinheiro", 35.0), 0.0)
        self.assertTrue(s.concluido())

    def test_troco(self):
        s = SplitPagamento(total=50.0)
        s.adicionar("dinheiro", 60.0)
        self.assertEqual(s.troco(), 10.0)


if __name__ == "__main__":
    unittest.main()
