"""Gráficos do relatório em PNG (matplotlib, backend Agg — sem janela).

Escolha de biblioteca: para embutir em PDF no back-end Python, matplotlib é a
opção mais confiável: é Python puro (pip, sem DLL de sistema), aceita fonte
UTF-8 com acentos e exporta PNG em alta resolução. Plotly precisaria do
kaleido; Chart.js/D3 exigiriam Node/canvas; ReportLab desenha gráfico na mão.

Saída: bytes PNG prontos para o ReportLab (ou para embutir em HTML).
"""

from __future__ import annotations

import io
from datetime import date

PRETO = "#000000"          # fonte dos gráficos: sempre preta
PALETA = ["#2a6b47", "#3d82a8", "#d99e2e", "#9e59a0", "#c7594f",
          "#668a4d", "#4d5a8c", "#8c7340", "#7a8b99", "#a3742f"]

DISPONIVEL = False
try:  # pragma: no cover - depende do ambiente
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    DISPONIVEL = True
except Exception:  # pragma: no cover
    matplotlib = None
    plt = None
    FuncFormatter = None


def _brl(v: float, _pos: int = 0) -> str:
    inteiro = f"{int(abs(v)):,}".replace(",", ".")
    centavos = f"{abs(v) - int(abs(v)):.2f}"[2:]
    return f"{'-' if v < 0 else ''}R$ {inteiro},{centavos}"


def _ax_linhas(ax, pontos: list[tuple[str, float]], titulo: str, cor: str = PALETA[0]):
    rotulos = [p[0] for p in pontos]
    valores = [p[1] for p in pontos]
    ax.plot(rotulos, valores, color=cor, linewidth=2, marker="o", markersize=4.5,
            markerfacecolor="#fff", markeredgewidth=1.8, markeredgecolor=cor)
    ax.fill_between(range(len(valores)), valores, color=cor, alpha=.12)
    ax.set_title(titulo, fontsize=11, color=PRETO, fontweight="bold", pad=10)
    ax.grid(axis="y", color="#e7ebe8", linewidth=.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c9d3cb")
    ax.yaxis.set_major_formatter(FuncFormatter(_brl))
    ax.tick_params(labelsize=8, colors=PRETO)
    if len(rotulos) > 10:
        passo = len(rotulos) // 10 + 1
        ax.set_xticks(range(0, len(rotulos), passo))
        ax.set_xticklabels([rotulos[i] for i in range(0, len(rotulos), passo)])
    if valores:
        ax.set_ylim(0, max(valores) * 1.18)


def _ax_pizza(ax, fatias: list[tuple[str, float]], titulo: str):
    dados = [(r, v) for r, v in fatias if v > 0]
    if not dados:
        ax.text(.5, .5, "Sem dados no periodo", ha="center", va="center", color=PRETO)
        ax.axis("off")
        return
    rotulos = [r for r, _ in dados]
    valores = [v for _, v in dados]
    fatias_pie = ax.pie(valores, labels=rotulos, colors=PALETA[:len(valores)],
                        autopct="%1.1f%%", startangle=90, counterclock=False,
                        textprops={"fontsize": 8.5, "color": PRETO, "fontfamily": "DejaVu Sans"},
                        wedgeprops={"edgecolor": "#fff", "linewidth": 1.5})
    for autotxt in fatias_pie[2]:
        autotxt.set_fontsize(8)
        autotxt.set_color(PRETO)
        autotxt.set_fontweight("bold")
    ax.set_title(titulo, fontsize=11, color=PRETO, fontweight="bold", pad=8)


def _ax_barras(ax, pontos: list[tuple[str, float]], titulo: str):
    rotulos = [r[:14] for r, _ in pontos]
    valores = [v for _, v in pontos]
    cores = PALETA[:len(valores)]
    barras = ax.bar(rotulos, valores, color=cores, edgecolor="none")
    barras[0].set_color(PALETA[0])
    ax.set_title(titulo, fontsize=11, color=PRETO, fontweight="bold", pad=10)
    ax.grid(axis="y", color="#e7ebe8", linewidth=.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c9d3cb")
    ax.yaxis.set_major_formatter(FuncFormatter(_brl))
    ax.tick_params(labelsize=8, colors=PRETO)
    ax.tick_params(axis="x", rotation=30 if len(rotulos) > 5 else 0)
    for b, v in zip(barras, valores):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:g}",
                ha="center", va="bottom", fontsize=7.5, color=PRETO)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight",
                facecolor="#ffffff", edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def _fig(largura: float, altura: float):
    return plt.subplots(figsize=(largura, altura), dpi=160)


def grafico_linhas(pontos: list[tuple[str, float]], titulo: str,
                   largura: float = 8.2, altura: float = 2.6) -> bytes:
    """Linha/área com eixo em R$. `pontos` = [(rótulo, valor)]."""
    if not DISPONIVEL:
        return b""
    fig, ax = _fig(largura, altura)
    _ax_linhas(ax, pontos, titulo)
    return _png(fig)


def grafico_pizza(fatias: list[tuple[str, float]], titulo: str,
                  largura: float = 5.6, altura: float = 3.2) -> bytes:
    if not DISPONIVEL:
        return b""
    fig, ax = _fig(largura, altura)
    _ax_pizza(ax, fatias, titulo)
    return _png(fig)


def grafico_barras(pontos: list[tuple[str, float]], titulo: str,
                   largura: float = 8.2, altura: float = 2.6) -> bytes:
    if not DISPONIVEL:
        return b""
    fig, ax = _fig(largura, altura)
    _ax_barras(ax, pontos, titulo)
    return _png(fig)


def _rotular(iso: str, por_hora: bool) -> str:
    if por_hora:
        return f"{str(iso)[:2]}h"
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day:02d}/{d.month:02d}"
    except Exception:
        return str(iso)


def graficos_do_relatorio(dados: dict, opcoes: dict) -> dict[str, bytes]:
    """Gera os PNGs pedidos nas opções: linhas/pizza/barras."""
    saida: dict[str, bytes] = {}
    if not DISPONIVEL:
        return saida
    por_hora = str(opcoes.get("agrupar") or "dia") == "hora"
    serie = dados.get("serie") or []
    campo = str(opcoes.get("campo_linhas") or "total")

    if opcoes.get("grafico_linhas") and serie:
        pontos = [(_rotular(r["rotulo"], por_hora), float(r.get(campo, 0) or 0)) for r in serie]
        saida["linhas"] = grafico_linhas(pontos, f"{campo.replace('_', ' ').title()} por "
                                                f"{'hora' if por_hora else 'dia'}")
    if opcoes.get("grafico_pizza"):
        fatia = str(opcoes.get("fatia_pizza") or "forma")
        if fatia == "produto":
            dados_pizza = [(p["nome"], p["total"]) for p in (dados.get("por_produto") or [])[:8]]
        elif fatia == "categoria":
            dados_pizza = [(c["categoria"], c["total"]) for c in (dados.get("por_categoria") or [])]
        else:
            dados_pizza = [(f["rotulo"], f["total"]) for f in (dados.get("por_forma") or [])]
        if dados_pizza:
            titulo = {"produto": "Participação por produto",
                      "categoria": "Participação por categoria"}.get(fatia, "Participação por forma de pagamento")
            saida["pizza"] = grafico_pizza(dados_pizza, titulo)
    if opcoes.get("grafico_barras"):
        pontos = [(p["nome"], p["quantidade"]) for p in (dados.get("por_produto") or [])[:10]]
        if pontos:
            saida["barras"] = grafico_barras(pontos, "Quantidade vendida por produto")
    return saida