"""Regressão: API não pode estourar com erro de thread do SQLite.

O FastAPI executa dependências (abertura do banco) e rotas em threads
diferentes do pool. Sem check_same_thread=False, qualquer tela que lê o
histórico quebra com sqlite3.ProgrammingError (HTTP 500) de forma intermitente.
Este teste dispara várias leituras em paralelo e exige 100% de sucesso.
"""

from __future__ import annotations

import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import create_app  # noqa: E402


class TesteHistoricoParalelo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = TestClient(cls.app, raise_server_exceptions=False)
        r = cls.client.post("/api/auth/login", json={"login": "admin", "senha": "admin123"})
        assert r.status_code == 200, r.text
        cls.token = r.json()["token"]

    def _get(self, path: str):
        return self.client.get(path, headers={"Authorization": f"Bearer {self.token}"})

    def test_leituras_em_paralelo_nao_quebram(self):
        dia = date.today().isoformat()
        caminhos = [
            f"/api/vendas?limite=200&dia={dia}",
            f"/api/caixa-operacoes?dia={dia}",
            "/api/vendas/totais",
            "/api/produtos",
            "/api/caixa/aberto",
            "/api/relatorios/mensal",
            "/api/vendas-limpar/preview?inicio=&fim=",
        ]
        erros: list[str] = []
        trava = threading.Lock()

        def bater(_: int):
            for path in caminhos:
                r = self._get(path)
                if r.status_code != 200:
                    with trava:
                        erros.append(f"{r.status_code} {path} {r.text[:150]}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(bater, range(8)))

        self.assertEqual([], erros, f"requisições paralelo falharam: {erros[:3]}")

    def test_conexao_aceita_troca_de_thread(self):
        """A mesma conexão pode ser criada numa thread e usada noutra."""
        from src.database.connection import connect, get_db_path

        conexao = connect(get_db_path())
        try:
            erro: list[BaseException] = []

            def usar():
                try:
                    conexao.execute("SELECT COUNT(*) FROM vendas").fetchone()
                except BaseException as e:  # pragma: no cover - só falha se voltar o bug
                    erro.append(e)

            t = threading.Thread(target=usar)
            t.start()
            t.join()
            self.assertEqual([], [f"{type(e).__name__}: {e}" for e in erro])
        finally:
            conexao.close()


if __name__ == "__main__":
    unittest.main()