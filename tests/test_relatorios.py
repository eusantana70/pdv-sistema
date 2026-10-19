"""Relatório de vendas: filtros, agregações e PDF com gráficos."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database.connection import connect  # noqa: E402
from database.schema import init_db  # noqa: E402
from database import repositories as repo  # noqa: E402
from services.pdf import texto_para_pdf  # noqa: E402
from services.relatorio_pdf import gerar_relatorio_pdf  # noqa: E402
from services import graficos as gfx  # noqa: E402
from services import relatorio_pdf as relpdf  # noqa: E402


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestRelatorioDetalhado(unittest.TestCase):
    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        init_db(self.db)
        self.conn = connect(self.db)
        pid = repo.criar_produto(self.conn, "Leite 1L", 5.0, 10)["id"]
        pid2 = repo.criar_produto(self.conn, "Pao", 3.0, 10, categoria="Padaria")["id"]
        hoje = date.today().isoformat()
        v1 = repo.criar_venda(self.conn, None,
                              [{"id_produto": pid, "quantidade": 2, "valor_unitario": 5.0}],
                              [{"metodo": "dinheiro", "valor": 10.0, "parcelas": 1}], 0)
        repo.criar_venda(self.conn, None,
                         [{"id_produto": pid2, "quantidade": 1, "valor_unitario": 3.0}],
                         [{"metodo": "pix", "valor": 3.0, "parcelas": 1}], 0)
        self.v1 = v1["id"]
        self.inicio = hoje
        self.fim = hoje

    def tearDown(self):
        self.conn.close()

    def _dados(self, **kw):
        return repo.relatorio_detalhado(self.conn, self.inicio, self.fim, **kw)

    def test_totais_nao_sao_duplicados_por_item(self):
        """Regressão: juntar pagamentos+itens inflava o total."""
        d = self._dados()
        soma_pag = sum(f["total"] for f in d["por_forma"])
        self.assertAlmostEqual(d["resumo"]["total"], soma_pag, places=2)
        self.assertAlmostEqual(d["resumo"]["total"], 13.0, places=2)
        self.assertEqual(d["resumo"]["vendas"], 2)

    def test_filtro_por_forma_de_pagamento(self):
        d = self._dados(formas=["pix"])
        self.assertAlmostEqual(d["resumo"]["total"], 3.0, places=2)
        self.assertEqual([f["forma"] for f in d["por_forma"]], ["pix"])
        d2 = self._dados(formas=["dinheiro", "pix"])
        self.assertEqual(d2["resumo"]["vendas"], 2)

    def test_filtro_por_produto_e_categoria(self):
        d = self._dados(produtos=["Leite"])
        self.assertAlmostEqual(d["resumo"]["total"], 10.0, places=2)
        self.assertEqual([p["nome"] for p in d["por_produto"]], ["Leite 1L"])
        d2 = self._dados(categorias=["Padaria"])
        self.assertEqual(d2["resumo"]["vendas"], 1)

    def test_agrupar_por_hora_e_por_dia(self):
        dia = self._dados(agrupar="dia")
        self.assertEqual(len(dia["serie"]), 1)
        hora = self._dados(agrupar="hora")
        self.assertTrue(hora["serie"])
        self.assertEqual(len(hora["serie"][0]["rotulo"]), 2)  # HH

    def test_periodo_sem_vendas(self):
        vazio = repo.relatorio_detalhado(self.conn, "2000-01-01", "2000-01-02")
        self.assertEqual(vazio["resumo"]["vendas"], 0)
        self.assertEqual(vazio["resumo"]["total"], 0)
        self.assertEqual(vazio["resumo"]["ticket_medio"], 0)

    def test_pdf_com_e_sem_graficos(self):
        d = self._dados()
        cfg = {"nome_fantasia": "Mercado Teste", "cnpj": "11.222.333/0001-44"}
        com = gerar_relatorio_pdf(d, cfg, {"grafico_linhas": True, "grafico_pizza": True,
                                           "grafico_barras": True, "campo_linhas": "total",
                                           "fatia_pizza": "forma"})
        self.assertTrue(com.startswith(b"%PDF-"))
        self.assertTrue(com.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/BaseFont /Helvetica", com)
        self.assertGreater(len(com), 3000)
        sem = gerar_relatorio_pdf(d, cfg, {"grafico_linhas": False, "grafico_pizza": False,
                                           "grafico_barras": False})
        self.assertTrue(sem.startswith(b"%PDF-"))
        self.assertLess(len(sem), len(com))  # sem gráficos é menor
        # pizza por produto e por categoria não quebram
        for fatia in ("produto", "categoria"):
            p = gerar_relatorio_pdf(d, cfg, {"grafico_pizza": True, "fatia_pizza": fatia})
            self.assertTrue(p.startswith(b"%PDF-"))
        # paisagem
        pais = gerar_relatorio_pdf(d, cfg, {"grafico_linhas": True, "paisagem": True})
        self.assertTrue(pais.startswith(b"%PDF-"))

    def test_pdf_texto_ainda_funciona(self):
        pdf = texto_para_pdf(["linha", "acentos ç ã é"], "t")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/BaseFont /Courier", pdf)

    def test_graficos_matplotlib_gera_png(self):
        """matplotlib deve gerar PNGs válidos (assinatura PNG no começo)."""
        if not gfx.DISPONIVEL:
            self.skipTest("matplotlib não instalado")
        dados = self._dados()
        pngs = gfx.graficos_do_relatorio(dados, {
            "grafico_linhas": True, "grafico_pizza": True, "grafico_barras": True,
            "campo_linhas": "total", "fatia_pizza": "forma", "agrupar": "dia"})
        self.assertEqual({"linhas", "pizza", "barras"}, set(pngs))
        for nome, png in pngs.items():
            self.assertTrue(png.startswith(PNG_MAGIC), f"{nome} não é PNG")
            self.assertGreater(len(png), 3000, f"{nome} muito pequeno")
        # pizza por produto e por categoria
        for fatia in ("produto", "categoria"):
            p = gfx.graficos_do_relatorio(dados, {"grafico_pizza": True, "fatia_pizza": fatia})
            self.assertIn("pizza", p)
            self.assertTrue(p["pizza"].startswith(PNG_MAGIC))
        # sem dados não quebra
        vazio = repo.relatorio_detalhado(self.conn, "2000-01-01", "2000-01-02")
        self.assertEqual({}, gfx.graficos_do_relatorio(vazio, {
            "grafico_linhas": True, "grafico_pizza": True, "grafico_barras": True}))
        # desligado = não gera
        self.assertEqual({}, gfx.graficos_do_relatorio(dados, {}))

    def test_pdf_usa_reportlab_quando_disponivel(self):
        d = self._dados()
        cfg = {"nome_fantasia": "Mercado Teste"}
        opcoes = {"grafico_linhas": True, "grafico_pizza": True, "grafico_barras": True}
        if relpdf.REPORTLAB_OK:
            pdf = gerar_relatorio_pdf(d, cfg, opcoes)
            self.assertIn(b"/Subtype /Image", pdf)   # gráficos embutidos
            self.assertIn(b"/Subtype /Image", pdf) if gfx.DISPONIVEL else None
            self.assertNotIn(b"/BaseFont /Courier", pdf)  # Helvetica do ReportLab
        # fallback (sem ReportLab) também gera PDF válido
        original = relpdf.REPORTLAB_OK
        relpdf.REPORTLAB_OK = False
        try:
            alt = gerar_relatorio_pdf(d, cfg, opcoes)
            self.assertTrue(alt.startswith(b"%PDF-"))
            self.assertTrue(alt.rstrip().endswith(b"%%EOF"))
        finally:
            relpdf.REPORTLAB_OK = original


if __name__ == "__main__":
    unittest.main()