"""M1/M2: repositories (perfis, produtos, config). Rodar: venv python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from database.connection import connect  # noqa: E402
from database.schema import init_db  # noqa: E402
from database import repositories as repo  # noqa: E402


class TestM1M2(unittest.TestCase):
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

    def test_perfil_crud(self):
        pid = repo.criar_perfil(self.conn, "Sorvetes", "21050010", "5102", "102", "0")
        self.assertGreater(pid, 0)
        perfis = repo.listar_perfis(self.conn)
        self.assertEqual(len(perfis), 1)
        repo.atualizar_perfil(self.conn, pid, "Sorvetes Atual", "21050010", "5102", "102", "0")
        self.assertEqual(repo.obter_perfil(self.conn, pid)["nome_perfil"], "Sorvetes Atual")
        with self.assertRaises(ValueError):
            repo.criar_perfil(self.conn, "", "21050010", "5102", "102", "0")

    def test_perfil_em_uso_nao_exclui(self):
        pid = repo.criar_perfil(self.conn, "P", "21050010", "5102", "102", "0")
        repo.criar_produto(self.conn, "Picole", 5.0, 1, pid)
        with self.assertRaises(ValueError):
            repo.excluir_perfil(self.conn, pid)

    def test_produto_fluxo_rapido(self):
        pid = repo.criar_perfil(self.conn, "P", "21050010", "5102", "102", "0")
        p = repo.criar_produto(self.conn, "Picole Chocolate", 5.50, 10, pid)
        self.assertRegex(p["codigo_interno"], r"^\d{4}$")
        # código opcional: omitido gera EAN aleatório único (8 dígitos, sem conflito)
        self.assertRegex(p["ean"], r"^\d{8}$")
        p2 = repo.criar_produto(self.conn, "Picole Menta", 5.50, 10, pid, ean="")
        self.assertRegex(p2["ean"], r"^\d{8}$")
        self.assertNotEqual(p["ean"], p2["ean"])
        # busca por nome e por código (autocomplete M4)
        self.assertEqual(len(repo.buscar_para_pdv(self.conn, "Chocolate")), 1)
        self.assertEqual(len(repo.buscar_para_pdv(self.conn, p["codigo_interno"])), 1)
        # desconto 10% de 5.50 -> 4.95
        self.assertAlmostEqual(repo.aplicar_desconto(self.conn, p["id"], 10), 4.95)
        repo.excluir_produto(self.conn, p["id"])
        repo.excluir_produto(self.conn, p2["id"])
        self.assertEqual(repo.listar_produtos(self.conn), [])

    def test_config(self):
        cfg = repo.obter_config(self.conn)
        self.assertEqual(cfg["id"], 1)
        repo.salvar_config(self.conn, "tok123", "https://fiscal/ex", "Termica-01")
        cfg2 = repo.obter_config(self.conn)
        self.assertEqual(cfg2["api_nfce_token"], "tok123")
        self.assertEqual(cfg2["impressora_nome"], "Termica-01")


if __name__ == "__main__":
    unittest.main()
