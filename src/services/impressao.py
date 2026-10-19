"""Nota NÃO fiscal (comprovante de venda) + impressão térmica.

O modelo do comprovante é configurável em Configurações → "Nota não fiscal"
(colunas recibo_*). A montagem é igual à que sai na impressora: monoespaçada,
alinhada à direita/centro, moeda no padrão brasileiro.
"""

from __future__ import annotations

from pathlib import Path

LARG_PADRAO = 48


# ---------- utilidades de formatação ----------

def brl(valor: float | str | None) -> str:
    """R$ 1.234,56 (padrão brasileiro)."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    inteiro = f"{int(abs(n)):,}".replace(",", ".")
    centavos = f"{abs(n) - int(abs(n)):.2f}"[2:]
    return f"R$ {inteiro},{centavos}"


def _centro(texto: str, larg: int) -> str:
    t = str(texto or "")[:larg]
    return t.center(larg)


def _linha_duplica(esq: str, dir: str, larg: int) -> str:
    """esquerda ......... direita (ex.: "TOTAL      R$ 55,00")."""
    e, d = str(esq or ""), str(dir or "")
    if len(e) + len(d) + 1 > larg:
        e = e[: max(1, larg - len(d) - 1)]
    return e + " " * (larg - len(e) - len(d)) + d


def _linha(char: str = "-", larg: int = LARG_PADRAO) -> str:
    return char * larg


def _quebra_nome(nome: str, larg: int) -> list[str]:
    """Quebra o nome do item em até 2 linhas sem cortar palavra ao meio."""
    n = str(nome or "").strip()
    if len(n) <= larg:
        return [n]
    corte = n.rfind(" ", 0, larg)
    if corte <= 0:
        return [n[:larg], n[larg:].strip()]
    return [n[:corte].strip(), n[corte + 1:].strip()]


def _qtd(q: float) -> str:
    return f"{q:g}"


# ---------- QR Code (link fixo da configuracao) ----------
# Biblioteca: "qrcode" (python-qrcode) ou "segno" — uma das duas basta.
#   pip install qrcode      (ou)      pip install segno
LIBERACAO_QR = ""

def _matriz_com_qrcode(txt: str) -> list[list[bool]]:
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=1, border=1)
    qr.add_data(txt)
    qr.make(fit=True)
    return [[bool(c) for c in linha] for linha in qr.get_matrix()]


def _matriz_com_segno(txt: str) -> list[list[bool]]:
    import segno
    qr = segno.make(txt, error="m")
    return [[bool(c) for c in linha] for linha in qr.matrix]


def matriz_qr(texto: str) -> list[list[bool]]:
    """Matriz do QR Code. Vazio se o texto for vazio ou faltar a biblioteca."""
    global LIBERACAO_QR
    txt = str(texto or "").strip()
    if not txt:
        return []
    if LIBERACAO_QR == "qrcode":
        return _matriz_com_qrcode(txt)
    if LIBERACAO_QR == "segno":
        return _matriz_com_segno(txt)
    for nome, fn in (("qrcode", _matriz_com_qrcode), ("segno", _matriz_com_segno)):
        try:
            matriz = fn(txt)
        except ImportError:
            continue
        except Exception:
            continue
        LIBERACAO_QR = nome
        return matriz
    return []


def qr_disponivel() -> bool:
    """True se alguma biblioteca de QR estiver instalada."""
    return bool(matriz_qr("https://pdv.local"))


def qr_ascii(matriz: list[list[bool]], larg: int | None = None) -> list[str]:
    """QR em '#' e espaço (1 caractere por módulo) — imprime em qualquer térmica.

    A impressora RAW usa cp850, então não serve usar blocos Unicode (█ ▀ ▄).
    Se o QR não couber na largura do papel, devolve lista vazia (o chamador
    imprime o link em texto).
    """
    if not matriz:
        return []
    n = len(matriz)
    if larg and n > larg:
        return []
    return ["".join("#" if m else " " for m in linha).rstrip() for linha in matriz]


def qr_svg(texto: str, tamanho_modulo: int = 6) -> str:
    """SVG do QR (para a prévia na tela). Vazio se não houver matriz."""
    matriz = matriz_qr(texto)
    if not matriz:
        return ""
    n = len(matriz)
    lado = n * tamanho_modulo
    blocos = "".join(
        f'<rect x="{j * tamanho_modulo}" y="{i * tamanho_modulo}" '
        f'width="{tamanho_modulo}" height="{tamanho_modulo}" fill="#000"/>'
        for i, linha in enumerate(matriz) for j, ativo in enumerate(linha) if ativo)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
            f'viewBox="0 0 {lado} {lado}" shape-rendering="crispEdges">'
            f'<rect width="{lado}" height="{lado}" fill="#fff"/>{blocos}</svg>')


# ---------- modelo do comprovante ----------

def montar_cupom(venda: dict, itens: list, pagamentos: list, cfg: dict | str | None = None,
                 nfe_link: str = "", troco: float | None = None,
                 atendente: str = "") -> str:
    # compatibilidade: a 4a posicao ja foi "nome da impressora" (string)
    if isinstance(cfg, str):
        cfg = {"impressora_nome": cfg}
    cfg = cfg or {}
    larg = 48
    try:
        larg = int(str(cfg.get("recibo_largura") or LARG_PADRAO))
    except (TypeError, ValueError):
        larg = LARG_PADRAO
    if larg not in (32, 48):
        larg = LARG_PADRAO

    def on(chave: str, padrao: bool = True) -> bool:
        """Chave ausente = padrão ligado (recibo tem que mostrar itens/pagamentos)."""
        v = cfg.get(chave)
        if v is None or v == "":
            return padrao
        return bool(int(v))

    nome_fantasia = str(cfg.get("nome_fantasia") or "").strip()
    razao = str(cfg.get("razao_social") or "").strip()
    titulo = str(cfg.get("recibo_titulo") or "").strip() or nome_fantasia or razao or "PDV"
    subtitulo = str(cfg.get("recibo_subtitulo") or "Cupom de venda - sem valor fiscal")
    rodape = str(cfg.get("recibo_rodape") or "Obrigado pela preferencia!")

    L: list[str] = []
    # ---- cabeçalho ----
    L.append(_centro(titulo.upper(), larg))
    if razao and razao.lower() != titulo.lower():
        L.append(_centro(razao, larg))
    if subtitulo:
        L.append(_centro(subtitulo, larg))
    if on("recibo_mostrar_cnpj"):
        cnpj = str(cfg.get("cnpj") or "").strip()
        if cnpj:
            L.append(_centro(f"CNPJ: {cnpj}", larg))
        end = str(cfg.get("cidade_uf") or "").strip()
        if end:
            L.append(_centro(end, larg))
    L.append(_linha("=", larg))

    # ---- venda ----
    data_hora = str(venda.get("data_hora") or "").replace("T", " ")
    cabecalho = f"Venda #{venda.get('id')}"
    if data_hora:
        cabecalho += f"  {data_hora}"
    L.append(cabecalho[:larg])
    if atendente.strip() and on("recibo_mostrar_atendente", False):
        L.append(f"Atendente: {atendente.strip()}"[:larg])
    L.append(_linha("-", larg))

    # ---- itens ----
    if on("recibo_mostrar_itens"):
        for it in itens:
            nome = str(it.get("nome") or f'Produto {it.get("id_produto")}')
            qtd = float(it.get("quantidade", 0) or 0)
            vu = float(it.get("valor_unitario", 0) or 0)
            sub = float(it.get("subtotal", 0) or 0)
            linhas = _quebra_nome(nome, larg - 12)
            for extra in linhas:
                L.append(extra[:larg])
            L.append(_linha_duplica(
                f"  {_qtd(qtd)} x {brl(vu)}", brl(sub), larg))
        L.append(_linha("-", larg))
    else:
        L.append(f"{len(itens)} item(ns)"[:larg])
        L.append(_linha("-", larg))

    # ---- total ----
    total = float(venda.get("total", 0) or 0)
    desconto = float(venda.get("desconto_percentual", 0) or 0)
    if desconto > 0:
        L.append(_linha_duplica(f"Desconto ({desconto:g}%)", "-", larg))
    L.append(_linha_duplica("TOTAL", brl(total), larg))

    # ---- pagamentos ----
    if on("recibo_mostrar_pagamentos"):
        for p in pagamentos:
            metodo = str(p.get("metodo") or "").capitalize()
            parcelas = int(p.get("parcelas") or 1)
            rotulo = f"{metodo} {parcelas}x" if metodo == "Credito" and parcelas > 1 else metodo
            L.append(_linha_duplica(rotulo, brl(p.get("valor", 0)), larg))
        if troco is not None and on("recibo_mostrar_troco"):
            L.append(_linha_duplica("Troco", brl(troco), larg))

    # ---- tributos federais / estaduais ----
    fed = float(cfg.get("recibo_tributos_federal") or 0)
    est = float(cfg.get("recibo_tributos_estadual") or 0)
    if on("recibo_mostrar_tributos") and (fed > 0 or est > 0):
        L.append(_linha("-", larg))
        L.append(f"Tributos (informativo)"[:larg])
        if fed > 0:
            L.append(_linha_duplica(f"  Federal {fed:g}%", brl(total * fed / 100), larg))
        if est > 0:
            L.append(_linha_duplica(f"  Estadual {est:g}%", brl(total * est / 100), larg))
        L.append(_linha_duplica(f"  Soma {(fed + est):g}%", brl(total * (fed + est) / 100), larg))

    # ---- fiscal (link da NFC-e, quando existir) ----
    if nfe_link and on("recibo_mostrar_qrcode"):
        L.append(_linha("-", larg))
        L.append("NFC-e / QR Code:")
        L.append(nfe_link[:larg])

    # ---- QR Code fixo (link da configuracao) ----
    link_qr = str(cfg.get("recibo_qrcode_link") or "").strip()
    if link_qr and on("recibo_mostrar_qrcode"):
        linhas_qr = qr_ascii(matriz_qr(link_qr), larg)
        L.append(_linha("-", larg))
        L.append(_centro("QR CODE", larg))
        if linhas_qr:
            for linha_qr in linhas_qr:
                L.append(_centro(linha_qr, larg))
        else:
            L.append(_centro("(link muito longo para o papel)", larg))
            L.append(link_qr[:larg])

    # ---- rodapé ----
    L.append(_linha("-", larg))
    aviso = str(cfg.get("recibo_aviso_trocas") or "").strip()
    if aviso and on("recibo_mostrar_aviso_trocas", False):
        L.append(_centro(aviso, larg))
    if rodape:
        L.append(_centro(rodape, larg))
    L.append("\n\n\n")
    return "\n".join(L)


def imprimir_texto_windows(texto: str, impressora_nome: str) -> tuple:
    """Envia texto para a térmica via win32print. Retorna (ok, msg)."""
    if not impressora_nome:
        return (False, "Nenhuma impressora configurada (Configurações → Impressão).")
    try:
        import win32print  # type: ignore
        import win32api  # type: ignore  # noqa: F401
    except ImportError:
        return (False, "pywin32 não instalado.")
    try:
        dados = texto.encode("cp850", errors="replace")
        h = win32print.OpenPrinter(impressora_nome)
        try:
            win32print.StartDocPrinter(h, 1, ("Comprovante PDV", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, dados)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return (True, "Comprovante enviado para a impressora.")
    except Exception as e:
        return (False, f"Falha ao imprimir: {e}")


def imprimir_cupom_venda(db_path, venda_id: int) -> tuple:
    """Carrega venda do banco, monta o comprovante e imprime.

    Sem impressora disponível (ou com falha na impressão) salva em PDF
    e devolve o caminho — a venda nunca fica sem documento.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from database.connection import connect
    from database import repositories as repo

    conn = connect(Path(db_path))
    try:
        venda = repo.obter_venda(conn, venda_id)
        itens = repo.listar_itens_venda(conn, venda_id)
        pagamentos = repo.listar_pagamentos_venda(conn, venda_id)
        cfg = repo.obter_config_full(conn)
    finally:
        conn.close()
    if not venda:
        return (False, "Venda não encontrada.")
    texto = montar_cupom(venda, itens, pagamentos, cfg,
                         venda.get("nfe_link_cupom", ""))
    ok, msg = imprimir_texto_windows(texto, cfg.get("impressora_nome", ""))
    if ok:
        return (True, msg)
    arquivo = salvar_pdf_recibo(venda, itens, pagamentos, cfg)
    return (True, f"{msg} Documento salvo em PDF: {arquivo}")


# ---------- PDF (fallback quando não há impressora) ----------

def _pasta(pasta_nome: str) -> Path:
    d = Path(__file__).resolve().parents[2] / "data" / pasta_nome
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _nome_seguro(texto: str, padrao: str) -> str:
    limpo = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(texto or ""))
    return (limpo[:40] or padrao)


def salvar_pdf_recibo(venda: dict, itens: list, pagamentos: list, cfg: dict) -> str:
    """Salva a nota NÃO fiscal em PDF (data/cupons) e devolve o caminho."""
    texto = montar_cupom(venda, itens, pagamentos, cfg, venda.get("nfe_link_cupom", ""))
    nome = f"cupom_{venda.get('id', 0)}_{_timestamp()}.pdf"
    destino = _pasta("cupons") / nome
    try:
        from services.pdf import salvar_pdf
    except ImportError:
        from src.services.pdf import salvar_pdf
    salvar_pdf(destino, texto.splitlines(), f"Comprovante venda {venda.get('id', '')}")
    return str(destino)


def linhas_nota_fiscal(venda: dict, itens: list, pagamentos: list, cfg: dict) -> list[str]:
    """Espelho da nota FISCAL em texto (o que vira PDF quando não há impressora)."""
    L: list[str] = []
    razao = str(cfg.get("razao_social") or cfg.get("nome_fantasia") or "Emitente")
    L.append(_centro(razao.upper(), 48))
    if cfg.get("cidade_uf"):
        L.append(_centro(str(cfg["cidade_uf"]), 48))
    if cfg.get("cnpj"):
        L.append(f"CNPJ: {cfg['cnpj']}".center(48))
    if cfg.get("ie"):
        L.append(f"IE: {cfg['ie']}".center(48))
    L.append(_linha("=", 48))
    L.append("DOCUMENTO AUXILIAR DA NOTA FISCAL (NFC-e / NF-e)")
    L.append(_linha("=", 48))
    modelo = str(cfg.get("modelo_doc") or "NFC-e")
    serie = str(cfg.get("serie") or "1")
    num = venda.get("id")
    L.append(f"Modelo: {modelo}   Serie: {serie}   Numero: {num}")
    L.append(f"Emissao: {str(venda.get('data_hora') or '').replace('T', ' ')}")
    L.append(f"Ambiente: {cfg.get('ambiente', 'homologacao')}")
    L.append(f"Status da nota: {venda.get('nfe_status', 'pendente')}")
    L.append(_linha("-", 48))
    for it in itens:
        nome = str(it.get("nome") or f'Produto {it.get("id_produto")}')
        qtd = float(it.get("quantidade", 0) or 0)
        sub = float(it.get("subtotal", 0) or 0)
        L.extend(_quebra_nome(nome, 48))
        L.append(_linha_duplica(f"  {_qtd(qtd)} un.", brl(sub), 48))
    L.append(_linha("-", 48))
    L.append(_linha_duplica("TOTAL DA NOTA", brl(venda.get("total", 0)), 48))
    for p in pagamentos:
        L.append(_linha_duplica(f"  {str(p.get('metodo', '')).capitalize()}",
                                brl(p.get("valor", 0)), 48))
    link = str(venda.get("nfe_link_cupom") or "")
    if link:
        L.append(_linha("-", 48))
        L.append("Consulta / QR Code:")
        L.extend(link[i:i + 48] for i in range(0, len(link), 48))
    xml = str(venda.get("nfe_xml") or "")
    if xml:
        L.append(_linha("-", 48))
        L.append("XML (inicio):")
        L.extend(xml[i:i + 48] for i in range(0, min(len(xml), 480), 48))
    return L


def salvar_pdf_fiscal(venda: dict, itens: list, pagamentos: list, cfg: dict) -> str:
    """Salva a nota FISCAL em PDF (data/notas) e devolve o caminho."""
    linhas = linhas_nota_fiscal(venda, itens, pagamentos, cfg)
    nome = f"nota_fiscal_{venda.get('id', 0)}_{_timestamp()}.pdf"
    destino = _pasta("notas") / nome
    try:
        from services.pdf import salvar_pdf
    except ImportError:
        from src.services.pdf import salvar_pdf
    salvar_pdf(destino, linhas, f"Nota fiscal venda {venda.get('id', '')}")
    return str(destino)