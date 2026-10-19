"""Geração de PDF sem dependências externas.

Fontes base-14 (Helvetica, Helvetica-Bold, Courier) com WinAnsiEncoding:
existem em qualquer leitor de PDF e cobrem os acentos do português.

Uso básico (texto):
    pdf.texto_para_pdf(linhas, "Título")

Uso com layout/desenho (relatórios com gráficos):
    doc = Documento("Relatório de vendas")
    doc.titulo("...", "...")
    doc.caixa(...)
    doc.grafico_linhas(...)
    doc.tabela(...)
    bytes_pdf = doc.finalizar()
"""

from __future__ import annotations

import math
from pathlib import Path

# A4 retrato / paisagem
A4_W, A4_H = 595.0, 842.0
MARGEM = 40.0

# paleta sóbria para os gráficos
CORES = [
    (0.16, 0.42, 0.28),   # verde
    (0.24, 0.51, 0.66),   # azul
    (0.85, 0.62, 0.18),   # âmbar
    (0.62, 0.35, 0.62),   # roxo
    (0.78, 0.35, 0.32),   # vermelho
    (0.40, 0.55, 0.30),   # oliva
    (0.30, 0.35, 0.55),   # azul escuro
    (0.55, 0.45, 0.25),   # sépia
]


def _esc(t: str) -> str:
    s = str(t or "").replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return s.encode("cp1252", errors="replace").decode("cp1252")


def _cor(c: tuple[float, float, float]) -> str:
    return "%.3f %.3f %.3f rg" % c


def _cor_linha(c: tuple[float, float, float]) -> str:
    return "%.3f %.3f %.3f RG" % c


class Documento:
    """Folha A4 com cursor vertical, tabelas e gráficos em vetor."""

    def __init__(self, titulo: str = "Documento", paisagem: bool = False,
                 margem: float = MARGEM):
        self.titulo_doc = titulo
        self.larg = A4_H if paisagem else A4_W
        self.alt = A4_W if paisagem else A4_H
        self.margem = margem
        self.conteudos: list[str] = []   # um por página
        self.atual: list[str] = []
        self.y = 0.0

    # ---------- infra ----------
    def _nova_pagina(self) -> None:
        if self.atual:
            self.conteudos.append("\n".join(self.atual))
        self.atual = []
        self.y = self.alt - self.margem

    @property
    def largura_util(self) -> float:
        return self.larg - self.margem * 2

    def espaco(self, altura: float) -> bool:
        return self.y - altura > self.margem + 24

    def garantir(self, altura: float) -> None:
        if not self.atual or not self.espaco(altura):
            self._nova_pagina()

    # ---------- texto ----------
    def texto(self, x: float, y: float, txt: str, tamanho: float = 9,
              fonte: str = "F2", cor=(0.1, 0.13, 0.11)) -> None:
        self.atual.append(
            f"BT {_cor(cor)} /{fonte} {tamanho:g} Tf ({_esc(txt)}) Tj ET"
            + f" 1 0 0 1 {x:.2f} {y:.2f} cm".replace("1 0 0 1", "0 0 0 0"))

    def texto_xy(self, x: float, y: float, txt: str, tamanho: float = 9,
                 fonte: str = "F2", cor=(0.1, 0.13, 0.11)) -> None:
        """Texto posicionado (BT com matriz de transformação)."""
        self.atual.append(
            f"BT {_cor(cor)} /{fonte} {tamanho:g} Tf "
            f"1 0 0 1 {x:.2f} {y - tamanho:.2f} Tm ({_esc(txt)}) Tj ET")

    def titulo(self, txt: str, subtitulo: str = "") -> None:
        self.garantir(46)
        self.y -= 18
        self.texto_xy(self.margem, self.y, txt, 17, "F3", (0.08, 0.2, 0.14))
        self.y -= 15
        if subtitulo:
            self.texto_xy(self.margem, self.y, subtitulo, 9.5, "F2", (0.42, 0.47, 0.44))
            self.y -= 4
        self.linha(self.margem, self.y, self.larg - self.margem, self.y,
                   (0.78, 0.82, 0.79), 0.8)
        self.y -= 14

    def secao(self, txt: str) -> None:
        self.garantir(34)
        self.y -= 6
        self.texto_xy(self.margem, self.y, txt, 11, "F3", (0.13, 0.3, 0.2))
        self.y -= 4
        self.linha(self.margem, self.y, self.larg - self.margem, self.y,
                   (0.7, 0.78, 0.72), 0.8)
        self.y -= 12

    def paragrafo(self, txt: str, tamanho: float = 9, cor=(0.25, 0.3, 0.27)) -> None:
        for linha in self._quebrar(txt, int(self.largura_util / (tamanho * 0.5))):
            self.garantir(tamanho + 3)
            self.y -= tamanho + 2
            self.texto_xy(self.margem, self.y, linha, tamanho, "F2", cor)

    @staticmethod
    def _quebrar(txt: str, largura: int) -> list[str]:
        palavras = str(txt).split()
        linhas, atual = [], ""
        for p in palavras:
            if len(atual) + len(p) + 1 > largura:
                linhas.append(atual)
                atual = p
            else:
                atual = f"{atual} {p}".strip()
        if atual:
            linhas.append(atual)
        return linhas or [""]

    # ---------- desenho ----------
    def linha(self, x1: float, y1: float, x2: float, y2: float,
              cor=(0.8, 0.83, 0.8), espessura: float = 0.7) -> None:
        self.atual.append(f"{_cor_linha(cor)} {espessura:g} w "
                          f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def caixa(self, x: float, y: float, w: float, h: float,
              preenchimento=(0.96, 0.97, 0.96), borda=(0.85, 0.89, 0.86)) -> None:
        self.atual.append(f"{_cor(borda)} 0.7 w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")
        self.atual.append(f"{_cor(preenchimento)} {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def poligono(self, pontos: list[tuple[float, float]], cor) -> None:
        if len(pontos) < 3:
            return
        d = [f"{_cor(cor)} {pontos[0][0]:.2f} {pontos[0][1]:.2f} m"]
        d += [f"{x:.2f} {y:.2f} l" for x, y in pontos[1:]]
        d.append("h f")
        self.atual.append(" ".join(d))

    # ---------- gráficos ----------
    def grafico_linhas(self, pontos: list[tuple[str, float]], titulo: str,
                       cor=(0.16, 0.42, 0.28), altura: float = 150,
                       valor_fmt=lambda v: f"{v:,.0f}".replace(",", ".")) -> None:
        self.garantir(altura + 46)
        topo = self.y - 16
        self.texto_xy(self.margem, topo, titulo, 9.5, "F3", (0.2, 0.26, 0.22))
        self.y = topo - 8
        if not pontos:
            self.texto_xy(self.margem, self.y, "Sem dados no periodo", 8.5, "F2", (0.55, 0.6, 0.56))
            self.y -= 14
            return
        base = self.y - altura
        maximo = max((v for _, v in pontos), default=0) or 1
        # grade + eixo Y
        for i in range(5):
            y = base + altura * i / 4
            self.linha(self.margem + 42, y, self.larg - self.margem - 6, y,
                       (0.9, 0.92, 0.9), 0.5)
            self.texto_xy(self.margem + 36, y + 2,
                          valor_fmt(maximo * i / 4), 6.5, "F1", (0.55, 0.6, 0.56))
        self.linha(self.margem + 42, base, self.larg - self.margem - 6, base,
                   (0.55, 0.62, 0.57), 0.9)
        n = len(pontos)
        largura_util = self.larg - self.margem - 6 - (self.margem + 42)
        passo = largura_util / max(1, n - 1) if n > 1 else 0
        coords = []
        for i, (rot, val) in enumerate(pontos):
            x = (self.margem + 42) + (passo * i if n > 1 else largura_util / 2)
            y = base + (val / maximo) * altura
            coords.append((x, y))
            if i % max(1, min(n, 12)) == 0 or i == n - 1:
                self.texto_xy(x - 9, base - 9, str(rot)[-5:], 6.2, "F1", (0.5, 0.56, 0.52))
        # área preenchida sob a linha + a linha
        poly = [(coords[0][0], base)] + coords + [(coords[-1][0], base)]
        suave = (min(1.0, cor[0] + .55), min(1.0, cor[1] + .55), min(1.0, cor[2] + .55))
        self.atual.append(f"{_cor(suave)} {poly[0][0]:.2f} {poly[0][1]:.2f} m " +
                          " ".join(f"{x:.2f} {y:.2f} l" for x, y in poly[1:]) + " h f")
        self.atual.append(f"{_cor_linha(cor)} 1.4 w " +
                          " ".join(f"{x:.2f} {y:.2f} l" for x, y in coords) + " S")
        for x, y in coords:
            self.atual.append(f"{_cor(cor)} {x - 1.4:.2f} {y - 1.4:.2f} 2.8 2.8 re f")
        self.y = base - 20

    def grafico_pizza(self, fatias: list[tuple[str, float]], titulo: str,
                     altura: float = 165) -> None:
        self.garantir(altura + 40)
        topo = self.y - 16
        self.texto_xy(self.margem, topo, titulo, 9.5, "F3", (0.2, 0.26, 0.22))
        self.y = topo - 10
        dados = [(r, v) for r, v in fatias if v > 0]
        if not dados:
            self.texto_xy(self.margem, self.y, "Sem dados no periodo", 8.5, "F2", (0.55, 0.6, 0.56))
            self.y -= 14
            return
        total = sum(v for _, v in dados) or 1
        cx = self.margem + 90
        cy = self.y - altura / 2
        r = min(altura / 2, 88)
        angulo = 90.0
        for i, (rot, val) in enumerate(dados):
            sweep = 360.0 * val / total
            cor = CORES[i % len(CORES)]
            passos = max(2, int(abs(sweep) / 3) + 1)
            pts = []
            for k in range(passos + 1):
                a = math.radians(angulo - sweep * k / passos)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            self.poligono(pts, cor)
            angulo -= sweep
        # legenda
        ly = cy + r - 6
        lx = cx + r + 22
        for i, (rot, val) in enumerate(dados):
            self.caixa(lx, ly - 3, 8, 8, preenchimento=CORES[i % len(CORES)], borda=CORES[i % len(CORES)])
            pct = 100.0 * val / total
            self.texto_xy(lx + 13, ly + 1, f"{rot}: R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                          7.5, "F2", (0.2, 0.26, 0.22))
            self.texto_xy(lx + 13, ly - 8, f"{pct:.1f}%".replace(".", ","), 6.8, "F1", (0.5, 0.56, 0.52))
            ly -= 20
        self.y = cy - r - 18

    def grafico_barras(self, pontos: list[tuple[str, float]], titulo: str,
                      altura: float = 150) -> None:
        self.garantir(altura + 40)
        topo = self.y - 16
        self.texto_xy(self.margem, topo, titulo, 9.5, "F3", (0.2, 0.26, 0.22))
        self.y = topo - 8
        if not pontos:
            self.y -= 14
            return
        base = self.y - altura
        maximo = max((v for _, v in pontos), default=0) or 1
        larg = self.larg - self.margem * 2
        n = len(pontos)
        bw = min(26, (larg - 30) / max(1, n) - 4)
        gap = (larg - n * bw) / max(1, n + 1)
        for i, (rot, val) in enumerate(pontos):
            x = self.margem + gap + i * (bw + gap)
            h = (val / maximo) * altura
            self.atual.append(f"{_cor(CORES[i % len(CORES)])} {x:.2f} {base:.2f} "
                              f"{bw:.2f} {h:.2f} re f")
            self.texto_xy(x + bw / 2 - 8, base - 9, str(rot)[-5:], 6.2, "F1", (0.5, 0.56, 0.52))
        self.linha(self.margem, base, self.larg - self.margem, base, (0.55, 0.62, 0.57), 0.9)
        self.y = base - 18

    # ---------- tabela ----------
    def tabela(self, cabecalho: list[str], linhas: list[list[str]],
               larguras: list[float] | None = None, tamanho: float = 7.8,
               alinhar: list[str] | None = None) -> None:
        larguras = larguras or [self.largura_util / len(cabecalho)] * len(cabecalho)
        alinhar = alinhar or ["left"] * len(cabecalho)
        altura_linha = tamanho + 6

        def desenha_cabecalho():
            self.garantir(altura_linha + 18)
            self.atual.append(f"{_cor((0.9, 0.93, 0.9))} {self.margem:.2f} {self.y - altura_linha - 2:.2f} "
                              f"{self.largura_util:.2f} {altura_linha + 3:.2f} re f")
            x = self.margem + 4
            for i, tit in enumerate(cabecalho):
                px = x + larguras[i] - (larguras[i] - 6 if alinhar[i] == "right" else 0)
                self.texto_xy(px, self.y - altura_linha + 1, str(tit)[:int(larguras[i] / (tamanho * 0.55))],
                              tamanho, "F3", (0.18, 0.3, 0.22))
                x += larguras[i]
            self.y -= altura_linha + 4

        desenha_cabecalho()
        for idx, linha in enumerate(linhas):
            if not self.espaco(altura_linha + 8):
                self._nova_pagina()
                desenha_cabecalho()
            self.y -= altura_linha
            if idx % 2 == 1:
                self.atual.append(f"{_cor((0.975, 0.98, 0.975))} {self.margem:.2f} {self.y - 2:.2f} "
                                  f"{self.largura_util:.2f} {altura_linha:.2f} re f")
            x = self.margem + 4
            for i, cel in enumerate(linha):
                txt = str(cel)[:int(larguras[i] / (tamanho * 0.55))]
                px = x + larguras[i] - (larguras[i] - 6 if alinhar[i] == "right" else 0)
                self.texto_xy(px, self.y, txt, tamanho, "F2", (0.22, 0.27, 0.24))
                x += larguras[i]
            self.linha(self.margem, self.y - 2, self.larg - self.margem, self.y - 2,
                       (0.9, 0.93, 0.91), 0.4)
        self.y -= 12

    def caixas_resumo(self, itens: list[tuple[str, str]]) -> None:
        """Cartões do resumo (rótulo + valor)."""
        if not itens:
            return
        largura = self.largura_util / len(itens)
        altura = 42
        self.garantir(altura + 10)
        for i, (rot, val) in enumerate(itens):
            x = self.margem + i * largura
            self.caixa(x + 2, self.y - altura, largura - 6, altura)
            self.texto_xy(x + 10, self.y - 14, rot, 7.2, "F2", (0.45, 0.5, 0.47))
            self.texto_xy(x + 10, self.y - 32, val, 12, "F3", (0.1, 0.28, 0.18))
        self.y -= altura + 16

    # ---------- saída ----------
    def finalizar(self) -> bytes:
        if self.atual:
            self.conteudos.append("\n".join(self.atual))
        if not self.conteudos:
            self.conteudos = [""]
        n = len(self.conteudos)
        id_catalog, id_pages = 1, 2
        ids_pagina = [3 + i for i in range(n)]
        ids_conteudo = [3 + n + i for i in range(n)]
        # fontes depois das páginas para não colidir com os ids
        f_helvetica = 3 + 2 * n
        f_bold = f_helvetica + 1
        f_courier = f_helvetica + 2
        total = f_courier
        objs: dict[int, bytes] = {}
        for i, conteudo in enumerate(self.conteudos):
            stream = conteudo.encode("cp1252", errors="replace")
            objs[ids_conteudo[i]] = (b"<< /Length " + str(len(stream)).encode() +
                                     b" >>\nstream\n" + stream + b"\nendstream")
            objs[ids_pagina[i]] = (
                f"<< /Type /Page /Parent {id_pages} 0 R "
                f"/MediaBox [0 0 {self.larg:g} {self.alt:g}] "
                f"/Resources << /Font << /F1 {f_helvetica} 0 R /F2 {f_helvetica} 0 R "
                f"/F3 {f_bold} 0 R /F4 {f_courier} 0 R >> >> "
                f"/Contents {ids_conteudo[i]} 0 R >>").encode()
        kids = " ".join(f"{p} 0 R" for p in ids_pagina)
        objs[id_pages] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
        objs[id_catalog] = f"<< /Type /Catalog /Pages {id_pages} 0 R >>".encode()
        objs[f_helvetica] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        objs[f_bold] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        objs[f_courier] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0] * (total + 1)
        for num in range(1, total + 1):
            offsets[num] = len(out)
            out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {total + 1}\n".encode() + b"0000000000 65535 f \n"
        for num in range(1, total + 1):
            out += f"{offsets[num]:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {total + 1} /Root {id_catalog} 0 R "
                f"/Info << /Title ({_esc(self.titulo_doc)}) >> >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode()
        return bytes(out)


def texto_para_pdf(linhas: list[str], titulo: str = "Documento") -> bytes:
    """PDF simples em monoespaçado (mantido para os comprovantes)."""
    d = Documento(titulo)
    d._nova_pagina()
    for linha in linhas:
        d.garantir(13)
        d.y -= 11.5
        d.texto_xy(d.margem, d.y, str(linha), 9, "F4", (0.1, 0.13, 0.11))
    return d.finalizar()


def salvar_pdf(destino, linhas: list[str], titulo: str = "Documento") -> str:
    """Grava o PDF de texto e devolve o caminho."""
    p = Path(destino)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(texto_para_pdf(linhas, titulo))
    return str(p)