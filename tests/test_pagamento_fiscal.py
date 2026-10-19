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
from services.impressao import montar_cupom, matriz_qr, qr_ascii, qr_svg  # noqa: E402


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
        self.assertIn("R$ 42,50", txt)          # moeda no padrão brasileiro
        self.assertIn("http://qr/3", txt)
        self.assertIn("Picole", txt)             # itens saem por padrão
        self.assertIn("Pix", txt)                # pagamentos saem por padrão

    def test_recibo_configuravel_respeita_opcoes(self):
        venda = {"id": 9, "total": 100.0, "data_hora": "2026-01-01 10:00:00"}
        itens = [{"nome": "Item", "quantidade": 1, "valor_unitario": 100.0, "subtotal": 100.0}]
        pays = [{"metodo": "dinheiro", "valor": 100.0, "parcelas": 1}]
        cfg = {
            "recibo_titulo": "Mercado do Ze",
            "recibo_subtitulo": "Consumidor final",
            "recibo_rodape": "Volte sempre",
            "recibo_largura": "32",
            "recibo_mostrar_cnpj": 0,
            "recibo_mostrar_itens": 0,
            "recibo_mostrar_pagamentos": 0,
            "recibo_mostrar_qrcode": 0,
            "cnpj": "00.000.000/0001-00",
        }
        txt = montar_cupom(venda, itens, pays, cfg, "http://qr/9", troco=5.0)
        linhas = txt.splitlines()
        self.assertTrue(all(len(l) <= 32 for l in linhas), linhas)
        self.assertIn("MERCADO DO ZE", txt)
        self.assertIn("Consumidor final", txt)
        self.assertIn("Volte sempre", txt)
        self.assertNotIn("00.000.000/0001-00", txt)   # CNPJ desligado
        self.assertNotIn("Item", txt)                 # itens desligados
        self.assertNotIn("Dinheiro", txt)             # pagamentos desligados
        self.assertNotIn("http://qr/9", txt)          # link/QR desligado
        self.assertIn("R$ 100,00", txt)

    def test_recibo_tributos_e_aviso_trocas(self):
        venda = {"id": 11, "total": 200.0, "data_hora": "2026-01-01 10:00:00"}
        itens = [{"nome": "Item", "quantidade": 1, "valor_unitario": 200.0, "subtotal": 200.0}]
        pays = [{"metodo": "pix", "valor": 200.0, "parcelas": 1}]
        cfg = {
            "recibo_tributos_federal": 12,
            "recibo_tributos_estadual": 18,
            "recibo_mostrar_tributos": 1,
            "recibo_mostrar_aviso_trocas": 1,
            "recibo_aviso_trocas": "Eventuais trocas somente mediante notinha",
        }
        txt = montar_cupom(venda, itens, pays, cfg)
        self.assertIn("Federal 12%", txt)
        self.assertIn("Estadual 18%", txt)
        self.assertIn("Soma 30%", txt)
        self.assertIn("R$ 24,00", txt)                 # 12% de 200
        self.assertIn("R$ 36,00", txt)                 # 18% de 200
        self.assertIn("Eventuais trocas somente mediante notinha", txt)
        # desligando, nada aparece
        cfg2 = {**cfg, "recibo_mostrar_tributos": 0, "recibo_mostrar_aviso_trocas": 0}
        txt2 = montar_cupom(venda, itens, pays, cfg2)
        self.assertNotIn("Federal 12%", txt2)
        self.assertNotIn("notinha", txt2)

    def test_qrcode_do_link_fixo(self):
        link = "https://minha-loja.com.br/consulta-venda"
        matriz = matriz_qr(link)
        self.assertTrue(matriz, "qrcode nao gerou matriz")
        linhas = qr_ascii(matriz, 48)
        self.assertTrue(linhas)
        # cabe no papel e usa apenas caracteres imprimiveis (cp850)
        self.assertTrue(all(len(l) <= 48 for l in linhas))
        self.assertTrue(all(set(l) <= {"#", " "} for l in linhas))
        # o mesmo link gera sempre o mesmo QR (fixo)
        self.assertEqual(linhas, qr_ascii(matriz_qr(link), 48))
        # QR não cabe em 32 colunas -> lista vazia (imprime o link em texto)
        self.assertEqual([], list(qr_ascii(matriz, 20)))
        svg = qr_svg(link)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("<rect", svg)
        self.assertEqual([], list(matriz_qr("")))

    def test_recibo_imprime_qr_e_link(self):
        venda = {"id": 12, "total": 50.0, "data_hora": "2026-01-01 10:00:00"}
        itens = [{"nome": "Item", "quantidade": 1, "valor_unitario": 50.0, "subtotal": 50.0}]
        pays = [{"metodo": "dinheiro", "valor": 50.0, "parcelas": 1}]
        cfg = {"recibo_qrcode_link": "https://loja.exemplo/pdv", "recibo_mostrar_qrcode": 1}
        txt = montar_cupom(venda, itens, pays, cfg)
        self.assertIn("QR CODE", txt)
        self.assertIn("#", txt)
        # sem link, nao imprime bloco de QR
        self.assertNotIn("QR CODE", montar_cupom(venda, itens, pays, {}))

    def test_pdf_sem_impressora(self):
        """Sem impressora, a nota (fiscal e não fiscal) é salva em PDF."""
        import tempfile
        from pathlib import Path
        from services.impressao import (
            imprimir_texto_windows, linhas_nota_fiscal, salvar_pdf_fiscal,
            salvar_pdf_recibo,
        )
        from services.pdf import texto_para_pdf

        # 1) sem impressora configurada, imprimir devolve erro (vira PDF depois)
        ok, msg = imprimir_texto_windows("qualquer", "")
        self.assertFalse(ok)
        self.assertIn("impressora", msg.lower())

        # 2) PDF gerado tem estrutura válida
        pdf = texto_para_pdf(["linha 1", "acentos: ç ã é", "R$ 10,00"], "Teste")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/BaseFont /Courier", pdf)
        self.assertEqual(pdf.count(b"/Type /Page "), 1)
        # multiplas paginas
        longo = texto_para_pdf([f"l{i}" for i in range(200)], "Longo")
        self.assertGreaterEqual(longo.count(b"/Type /Page "), 3)  # paginou

        # 3) espelho fiscal tem os dados da nota
        venda = {"id": 7, "total": 90.0, "data_hora": "2026-01-01 10:00:00",
                 "nfe_status": "autorizado", "nfe_link_cupom": "http://nota/1",
                 "nfe_xml": "<nfe><infNFe Id=\"ABC\"/></nfe>"}
        itens = [{"nome": "Produto", "quantidade": 2, "valor_unitario": 45.0, "subtotal": 90.0}]
        pays = [{"metodo": "pix", "valor": 90.0, "parcelas": 1}]
        cfg = {"razao_social": "Mercado Teste", "cnpj": "11.222.333/0001-44",
               "modelo_doc": "NFC-e", "serie": "1", "ambiente": "homologacao"}
        espelho = "\n".join(linhas_nota_fiscal(venda, itens, pays, cfg))
        self.assertIn("DOCUMENTO AUXILIAR DA NOTA FISCAL", espelho)
        self.assertIn("Mercado Teste".upper(), espelho)
        self.assertIn("R$ 90,00", espelho)
        self.assertIn("http://nota/1", espelho)

        # 4) salvam em disco (pasta temporária via patched _pasta)
        pasta = Path(tempfile.mkdtemp())
        import services.impressao as imp
        original = imp._pasta
        imp._pasta = lambda nome: pasta / nome
        try:
            p1 = Path(salvar_pdf_recibo(venda, itens, pays, cfg))
            p2 = Path(salvar_pdf_fiscal(venda, itens, pays, cfg))
        finally:
            imp._pasta = original
        self.assertTrue(p1.exists() and p1.suffix == ".pdf")
        self.assertTrue(p2.exists() and p2.suffix == ".pdf")
        self.assertEqual(p1.read_bytes()[:5], b"%PDF-")
        self.assertEqual(p2.read_bytes()[:5], b"%PDF-")

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
