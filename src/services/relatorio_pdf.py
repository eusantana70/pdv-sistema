"""Relatório de vendas em PDF — ReportLab + gráficos do matplotlib.

Escolha de biblioteca para o PDF: ReportLab. Ela é Python puro (pip, sem DLL de
sistema como o WeasyPrint), tem controle preciso de layout (platypus: tabela,
cabeçalho/rodapé, quebras) e embute PNG do matplotlib nativamente. Puppeteer
exigiria Chrome/Node; IronPDF é comercial; desenhar na mão dá layout limitado.

Se o ReportLab ou o matplotlib não estiverem instalados, cai automaticamente
no gerador próprio de `services.pdf` — o relatório nunca deixa de ser gerado.
"""

from __future__ import annotations

from datetime import date, datetime

from . import pdf as pdf_proprio

try:  # pragma: no cover - depende do ambiente
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)
    REPORTLAB_OK = True
except Exception:  # pragma: no cover
    REPORTLAB_OK = False

from . import graficos as gfx


def _brl(valor: float | None) -> str:
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    inteiro = f"{int(abs(v)):,}".replace(",", ".")
    centavos = f"{abs(v) - int(abs(v)):.2f}"[2:]
    return f"R$ {inteiro},{centavos}"


def _pct(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def _data_br(iso: str) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    except Exception:
        return str(iso or "-")


# ---------------------------------------------------------------- ReportLab

VERDE = colors.HexColor("#2a6b47")
VERDE_CLARO = colors.HexColor("#e7f2ea")
CINZA = colors.HexColor("#5e6962")
CINZA_CLARO = colors.HexColor("#8a958e")
BORDA = colors.HexColor("#c9d3cb")
FUNDO = colors.HexColor("#f4f6f4")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold",
                                 fontSize=17, textColor=colors.HexColor("#143a26"), spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName="Helvetica",
                              fontSize=9.5, textColor=CINZA, spaceAfter=10),
        "secao": ParagraphStyle("secao", parent=base["Heading2"], fontName="Helvetica-Bold",
                                fontSize=12, textColor=colors.HexColor("#1f5c3c"),
                                spaceBefore=12, spaceAfter=6),
        "corpo": ParagraphStyle("corpo", parent=base["Normal"], fontName="Helvetica",
                                fontSize=8.5, textColor=colors.HexColor("#3d4a42")),
        "nota": ParagraphStyle("nota", parent=base["Normal"], fontName="Helvetica",
                               fontSize=7.5, textColor=CINZA_CLARO),
        "centro": ParagraphStyle("centro", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=8.5, alignment=TA_CENTER),
        "dir": ParagraphStyle("dir", parent=base["Normal"], fontName="Helvetica",
                              fontSize=8.5, alignment=TA_RIGHT),
        "dirb": ParagraphStyle("dirb", parent=base["Normal"], fontName="Helvetica-Bold",
                               fontSize=8.5, alignment=TA_RIGHT),
        "celula": ParagraphStyle("celula", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=8, textColor=colors.HexColor("#2b362f")),
        "celulab": ParagraphStyle("celulab", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=8, textColor=colors.HexColor("#1f5c3c")),
    }


def _cabalho(canvas, doc):
    """Faixa com nome da loja + linha verde em todas as páginas."""
    loja = getattr(doc, "loja", "PDV Lumina")
    w, h = doc.pagesize
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#143a26"))
    canvas.rect(0, h - 14 * mm, w, 14 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(14 * mm, h - 9 * mm, loja[:52])
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 14 * mm, h - 9 * mm, "Relatório de vendas")
    canvas.setStrokeColor(VERDE)
    canvas.setLineWidth(2)
    canvas.line(0, h - 14 * mm, w, h - 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(CINZA_CLARO)
    canvas.drawString(14 * mm, 9 * mm,
                      f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} - PDV Lumina")
    canvas.drawRightString(w - 14 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _tabela(dados: list[list[str]], larguras: list[float], est, direita: list[int]) -> Table:
    t = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f5c3c")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#2b362f")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, VERDE),
    ]
    for linha in range(2, len(dados), 2):
        estilo.append(("BACKGROUND", (0, linha), (-1, linha), colors.HexColor("#fafbfa")))
    for col in direita:
        estilo.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


def _cartoes(resumo: dict) -> Table:
    itens = [("TOTAL VENDIDO", _brl(resumo["total"])), ("VENDAS", f"{int(resumo['vendas'])}"),
             ("ITENS", f"{resumo['itens']:g}"), ("TICKET MÉDIO", _brl(resumo["ticket_medio"])),
             ("DESCONTO MÉDIO", _pct(resumo["desconto_medio"]))]
    dados = [[Paragraph(r, ParagraphStyle(f"lbl{i}", fontName="Helvetica", fontSize=6.8, textColor=CINZA))
              for i, (r, _) in enumerate(itens)],
             [Paragraph(v, ParagraphStyle(f"val{i}", fontName="Helvetica-Bold", fontSize=12.5, textColor=VERDE))
              for i, (_, v) in enumerate(itens)]]
    t = Table(dados, colWidths=[36 * mm] * len(itens))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def gerar_relatorio_pdf(dados: dict, cfg: dict, opcoes: dict) -> bytes:
    """Relatório completo em PDF (ReportLab) com fallback próprio se faltar lib."""
    if not REPORTLAB_OK:
        return _fallback(dados, cfg, opcoes)
    try:
        return _reportlab(dados, cfg, opcoes)
    except Exception:
        return _fallback(dados, cfg, opcoes)


def _reportlab(dados: dict, cfg: dict, opcoes: dict) -> bytes:
    import io

    resumo = dados["resumo"]
    serie = dados.get("serie") or []
    por_forma = dados.get("por_forma") or []
    por_produto = dados.get("por_produto") or []
    por_categoria = dados.get("por_categoria") or []
    agrupar = str(opcoes.get("agrupar") or "dia")
    est = _estilos()
    empresa = str(cfg.get("nome_fantasia") or cfg.get("razao_social") or "PDV Lumina")

    buf = io.BytesIO()
    tam = landscape(A4) if opcoes.get("paisagem") else A4
    doc = SimpleDocTemplate(buf, pagesize=tam, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=20 * mm, bottomMargin=14 * mm,
                            title="Relatorio de vendas", author="PDV Lumina")
    doc.loja = empresa
    largura_util = tam[0] - 28 * mm

    filtros = dados.get("filtros") or {}
    desc = []
    if filtros.get("formas"):
        desc.append("formas: " + ", ".join(str(f).title() for f in filtros["formas"]))
    if filtros.get("categorias"):
        desc.append("categorias: " + ", ".join(filtros["categorias"]))
    if filtros.get("produtos"):
        desc.append("produtos: " + ", ".join(filtros["produtos"]))

    e = []
    e.append(Paragraph("RELATÓRIO DE VENDAS", est["titulo"]))
    periodo = (f"Vendas por hora — {filtros.get('dia') or ''}" if agrupar == "hora"
               else f"Vendas de {_data_br(dados['inicio'])} a {_data_br(dados['fim'])}")
    e.append(Paragraph(f"{empresa} &nbsp;|&nbsp; {periodo}", est["sub"]))
    e.append(Paragraph("Filtros aplicados: " + (" | ".join(desc) if desc else "nenhum filtro"), est["nota"]))
    e.append(Spacer(1, 5 * mm))
    e.append(_cartoes(resumo))

    pngs = gfx.graficos_do_relatorio(dados, dict(opcoes, agrupar=agrupar))

    if "linhas" in pngs:
        e.append(Paragraph("Gráfico de vendas", est["secao"]))
        e.append(Image(io.BytesIO(pngs["linhas"]), width=largura_util, height=largura_util * 0.30))
    if "pizza" in pngs:
        e.append(Paragraph("Gráfico de pizza", est["secao"]))
        img = Image(io.BytesIO(pngs["pizza"]), width=largura_util * 0.62, height=largura_util * 0.34)
        img.hAlign = "CENTER"
        e.append(img)
    if "barras" in pngs:
        e.append(Paragraph("Produtos mais vendidos", est["secao"]))
        e.append(Image(io.BytesIO(pngs["barras"]), width=largura_util, height=largura_util * 0.26))

    if serie:
        e.append(Paragraph("Detalhamento por período", est["secao"]))
        cabec = ["Período", "Vendas", "Dinheiro", "Crédito", "Débito", "PIX", "Total"]
        linhas = [[(_data_br(s["rotulo"]) if agrupar == "dia" else f"{s['rotulo']}h"),
                   str(int(s["vendas"])), _brl(s["dinheiro"]), _brl(s["credito"]),
                   _brl(s["debito"]), _brl(s["pix"]), _brl(s["total"])] for s in serie]
        larguras = [largura_util * w for w in (.17, .10, .14, .14, .14, .13, .18)]
        e.append(_tabela([cabec] + linhas, larguras, est, [1, 2, 3, 4, 5, 6]))

    if por_forma:
        e.append(Paragraph("Formas de pagamento", est["secao"]))
        base = sum(f["total"] for f in por_forma) or 1
        linhas = [[f["rotulo"], f"{int(f['vendas'])} venda(s)", _brl(f["total"]),
                   _pct(100 * f["total"] / base)] for f in por_forma]
        e.append(_tabela([["Forma", "Vendas", "Total", "Participação"]] + linhas,
                         [largura_util * w for w in (.34, .22, .24, .20)], est, [1, 2, 3]))

    if por_produto:
        e.append(Paragraph("Produtos vendidos", est["secao"]))
        base = sum(p["total"] for p in por_produto) or 1
        linhas = [[p["nome"][:40], p["categoria"] or "—", f"{p['quantidade']:g}",
                   _brl(p["total"]), _pct(100 * p["total"] / base)] for p in por_produto]
        e.append(_tabela([["Produto", "Categoria", "Qtd", "Total", "Part."]] + linhas,
                         [largura_util * w for w in (.34, .22, .12, .19, .13)], est, [2, 3, 4]))

    if por_categoria:
        e.append(Paragraph("Categorias", est["secao"]))
        linhas = [[c["categoria"], f"{c['quantidade']:g}", _brl(c["total"])] for c in por_categoria]
        e.append(_tabela([["Categoria", "Qtd", "Total"]] + linhas,
                         [largura_util * w for w in (.5, .2, .3)], est, [1, 2]))

    e.append(Spacer(1, 4 * mm))
    e.append(Paragraph("Relatório gerado automaticamente pelo PDV Lumina. "
                       "Valores consideram vendas concluídas (canceladas excluídas).", est["nota"]))
    doc.build(e, onFirstPage=_cabalho, onLaterPages=_cabalho)
    return buf.getvalue()


def _fallback(dados: dict, cfg: dict, opcoes: dict) -> bytes:
    """Gerador próprio quando ReportLab/matplotlib não estão disponíveis."""
    resumo = dados["resumo"]
    linhas = [
        "RELATORIO DE VENDAS",
        str(cfg.get("nome_fantasia") or cfg.get("razao_social") or "PDV Lumina"),
        f"Periodo: {dados['inicio']} a {dados['fim']}",
        f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "=" * 48,
        f"TOTAL VENDIDO........... {_brl(resumo['total'])}",
        f"VENDAS................. {int(resumo['vendas'])}",
        f"ITENS.................. {resumo['itens']:g}",
        f"TICKET MEDIO............ {_brl(resumo['ticket_medio'])}",
        "-" * 48,
        "FORMAS DE PAGAMENTO",
    ]
    base = sum(f["total"] for f in dados.get("por_forma") or []) or 1
    for f in dados.get("por_forma") or []:
        linhas.append(f"  {f['rotulo']:<16}{_brl(f['total']):>14}{_pct(100 * f['total'] / base):>9}")
    linhas.append("-" * 48)
    linhas.append("PRODUTOS")
    for p in dados.get("por_produto") or []:
        linhas.append(f"  {p['nome'][:20]:<21}{p['quantidade']:>5g} un{_brl(p['total']):>16}")
    return pdf_proprio.texto_para_pdf(linhas, "Relatorio de vendas")