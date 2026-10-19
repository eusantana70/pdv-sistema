"""Importação de produtos a partir de arquivos (CSV/TXT, XLSX, PDF e DOCX).

Cada linha do arquivo deve conter um produto. Colunas reconhecidas (case insensitive,
aceita também os nomes em portugues):

nome / produto / descricao          (obrigatorio)
sku / codigo / codigo_interno / ean / codigo_barras
categoria / categoria_produto
preco / preco_venda / valor / valor_unitario
estoque / quantidade / quantidade_estoque / qtd
unidade / unidade_medida
cor
validade / data_validade
"""

from __future__ import annotations

import io
from pathlib import Path

# Mapeia nomes de coluna (em qualquer idioma/case) para o nome padrao interno
COLUNAS_MAPEADAS: dict[str, str] = {
    # nome do produto
    "nome": "nome", "produto": "nome", "descricao": "nome", "descricao do produto": "nome",
    "nome do produto": "nome", "item": "nome",
    # codigo / sku / ean
    "sku": "sku", "codigo": "sku", "codigo_interno": "sku", "ean": "sku",
    "codigo_barras": "sku", "codigo de barras": "sku", "codigo de barras do produto": "sku",
    # categoria
    "categoria": "categoria", "categoria_produto": "categoria",
    "categoria do produto": "categoria", "grupo": "categoria",
    # preco
    "preco": "preco_venda", "preco_venda": "preco_venda", "preco de venda": "preco_venda",
    "valor": "preco_venda", "valor_unitario": "preco_venda", "valor unitario": "preco_venda",
    "preco unitario": "preco_venda", "valor de venda": "preco_venda",
    # estoque
    "estoque": "quantidade_estoque", "quantidade": "quantidade_estoque",
    "quantidade_estoque": "quantidade_estoque", "qtd": "quantidade_estoque",
    "qtd_estoque": "quantidade_estoque", "qtde": "quantidade_estoque",
    # unidade
    "unidade": "unidade_medida", "unidade_medida": "unidade_medida",
    "unidade de medida": "unidade_medida", "unidade medida": "unidade_medida",
    # cor
    "cor": "cor",
    # validade
    "validade": "validade", "data_validade": "validade", "data de validade": "validade",
    "validade do produto": "validade",
}


def _normalizar_colunas(colunas: list[str]) -> dict[str, str]:
    """Mapeia nomes de coluna do arquivo para os nomes padronizados."""
    mapeamento: dict[str, str] = {}
    for coluna in colunas:
        chave = str(coluna).strip().lower()
        if chave in COLUNAS_MAPEADAS:
            mapeamento[coluna] = COLUNAS_MAPEADAS[chave]
    return mapeamento


def _valor(linha: dict, chave: str):
    """Pega o valor de uma linha pelo nome padronizado (tenta varias grafias)."""
    # tenta chave padronizada primeiro
    for chave_original, chave_padrao in linha.items():
        if chave_padrao == chave:
            return chave_original
    # fallback: tenta qualquer coluna cujo nome padronizado seja a chave
    return None


def ler_csv(caminho: Path) -> list[dict]:
    """Lê arquivo CSV ou TXT (separador detectado automaticamente)."""
    import csv

    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        # detecta delimitador automaticamente
        amostra = f.read(4096)
        f.seek(0)
        delimitador = ","
        try:
            dialeto = csv.Sniffer().sniff(amostra, delimiters=",\t;|")
            delimitador = dialeto.delimiter
        except Exception:
            # fallback: conta ocorrências de cada delimitador na amostra
            contagens = {d: amostra.count(d) for d in [",", ";", "\t", "|"]}
            delimitador = max(contagens, key=contagens.get) if any(contagens.values()) else ","
        leitor = csv.DictReader(f, delimiter=delimitador)
        mapeou = _normalizar_colunas(leitor.fieldnames or [])
        linhas = []
        for linha in leitor:
            if not any(str(v or "").strip() for v in linha.values()):
                continue
            mapeada = {mapeou.get(k, k): v for k, v in linha.items() if v}
            linhas.append(mapeada)
        return linhas


def ler_excel(caminho: Path) -> list[dict]:
    """Lê arquivo XLSX/XLS (primeira aba)."""
    import pandas as pd

    df = pd.read_excel(caminho, dtype=str, keep_default_na=False)
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    df.columns = [str(c).strip() for c in df.columns]
    mapeou = _normalizar_colunas(list(df.columns))
    linhas = []
    for _, linha in df.iterrows():
        mapeada = {}
        for coluna_original, valor in linha.items():
            chave = mapeou.get(coluna_original, coluna_original)
            if pd.notna(valor) and str(valor).strip():
                mapeada[chave] = str(valor).strip()
        if mapeada:
            linhas.append(mapeada)
    return linhas


def ler_pdf(caminho: Path) -> list[dict]:
    """Lê PDF extraindo texto e tentando interpretar cada linha como produto."""
    import pdfplumber

    linhas: list[str] = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            for linha in texto.split("\n"):
                linha = linha.strip()
                if linha:
                    linhas.append(linha)
    return _converter_texto_linhas(linhas)


def ler_docx(caminho: Path) -> list[dict]:
    """Lê DOCX pegando cada paragrafo como uma linha."""
    from docx import Document

    doc = Document(caminho)
    linhas = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return _converter_texto_linhas(linhas)


def _converter_texto_linhas(linhas: list[str]) -> list[dict]:
    """Tenta transformar linhas de texto livre em produtos.
    Espera algo como: 'Nome do Produto; SKU; Categoria; 10.00; 5'
    ou simplesmente um nome por linha (preco/estoque ficam zerados)."""
    resultados: list[dict] = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        # tenta separar por ponto-e-virgula, tab ou virgula
        if ";" in linha:
            partes = [p.strip() for p in linha.split(";")]
        elif "\t" in linha:
            partes = [p.strip() for p in linha.split("\t")]
        elif "," in linha and len(linha.split(",")) >= 3:
            partes = [p.strip() for p in linha.split(",")]
        else:
            partes = [linha]

        mapeada: dict = {}
        if len(partes) >= 1:
            mapeada["nome"] = partes[0]
        if len(partes) >= 2:
            mapeada["sku"] = partes[1]
        if len(partes) >= 3:
            mapeada["categoria"] = partes[2]
        if len(partes) >= 4:
            mapeada["preco_venda"] = partes[3]
        if len(partes) >= 5:
            mapeada["quantidade_estoque"] = partes[4]
        if len(partes) >= 6:
            mapeada["unidade_medida"] = partes[5]
        if len(partes) >= 7:
            mapeada["cor"] = partes[6]
        if len(partes) >= 7:
            mapeada["validade"] = partes[6]
        if len(partes) >= 8:
            mapeada["validade"] = partes[7]

        if mapeada.get("nome"):
            resultados.append(mapeada)
    return resultados


def ler_arquivo(caminho: str | Path) -> list[dict]:
    """Lê qualquer arquivo suportado e retorna lista de dicionarios mapeados."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    extensao = caminho.suffix.lower()
    if extensao in (".csv", ".txt", ".tsv"):
        return ler_csv(caminho)
    if extensao in (".xlsx", ".xls"):
        return ler_excel(caminho)
    if extensao == ".pdf":
        return ler_pdf(caminho)
    if extensao in (".docx", ".doc"):
        return ler_docx(caminho)
    raise ValueError(f"Extensão não suportada: {extensao}")


def validar_e_normalizar(linhas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Valida linhas brutas e retorna (validos, erros)."""
    validos: list[dict] = []
    erros: list[dict] = []

    for indice, linha in enumerate(lista := linhas, start=1):
        erros_linha: list[str] = []

        nome = (linha.get("nome") or "").strip()
        if not nome:
            erros_linha.append("nome obrigatorio")

        sku = (linha.get("sku") or "").strip() or None
        categoria = (linha.get("categoria") or "").strip() or None
        unidade = (linha.get("unidade_medida") or "").strip() or None
        cor = (linha.get("cor") or "").strip() or None
        validade = (linha.get("validade") or "").strip() or None

        preco = 0.0
        preco_raw = (linha.get("preco_venda") or "").strip()
        if preco_raw:
            try:
                preco = float(preco_raw.replace(",", "."))
            except ValueError:
                erros_linha.append(f"preco invalido: {preco_raw}")
                preco = 0.0

        estoque = 0
        estoque_raw = (linha.get("quantidade_estoque") or "").strip()
        if estoque_raw:
            try:
                estoque = int(float(estoque_raw.replace(",", ".")))
            except ValueError:
                erros_linha.append(f"quantidade invalida: {estoque_raw}")
                estoque = 0

        if erros_linha:
            erros.append({"linha": indice, "nome": nome or "(sem nome)", "erros": erros_linha})
            continue

        validos.append({
            "nome": nome,
            "sku": sku,
            "categoria": categoria,
            "preco_venda": preco,
            "quantidade_estoque": estoque,
            "unidade_medida": unidade,
            "cor": cor,
            "validade": validade,
        })

    return validos, erros