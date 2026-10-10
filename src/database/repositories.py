"""Repositories SQLite — M1 (perfis/config) e M2 (produtos)."""

from __future__ import annotations

import sqlite3


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


# ---------- Perfis fiscais (M1) ----------

def listar_perfis(conn: sqlite3.Connection) -> list:
    cur = conn.execute("SELECT * FROM perfis_fiscais ORDER BY nome_perfil")
    return [dict(r) for r in cur.fetchall()]


def obter_perfil(conn: sqlite3.Connection, perfil_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM perfis_fiscais WHERE id = ?", (perfil_id,))
    return _row_to_dict(cur.fetchone())


def criar_perfil(conn: sqlite3.Connection, nome: str, ncm: str,
                 cfop: str = "5102", csosn: str = "", origem: str = "") -> int:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome do perfil é obrigatório.")
    if not (ncm or "").strip():
        raise ValueError("NCM é obrigatório.")
    if not (csosn or "").strip():
        raise ValueError("CSOSN é obrigatório.")
    cfop = (cfop or "5102").strip() or "5102"
    cur = conn.execute(
        "INSERT INTO perfis_fiscais (nome_perfil, ncm, cfop, csosn, origem)"
        " VALUES (?, ?, ?, ?, ?)",
        (nome, ncm.strip(), cfop, csosn.strip(), (origem or "").strip()),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_perfil(conn: sqlite3.Connection, perfil_id: int, nome: str, ncm: str,
                      cfop: str, csosn: str, origem: str) -> None:
    if not (nome or "").strip():
        raise ValueError("Nome do perfil é obrigatório.")
    conn.execute(
        "UPDATE perfis_fiscais SET nome_perfil=?, ncm=?, cfop=?, csosn=?, origem=?"
        " WHERE id=?",
        (nome.strip(), ncm.strip(), (cfop or "5102").strip() or "5102",
         csosn.strip(), (origem or "").strip(), perfil_id),
    )
    conn.commit()


def excluir_perfil(conn: sqlite3.Connection, perfil_id: int) -> None:
    try:
        cur = conn.execute("DELETE FROM perfis_fiscais WHERE id = ?", (perfil_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError("Perfil não encontrado.")
    except sqlite3.IntegrityError as e:
        raise ValueError("Perfil em uso por produtos; não pode excluir.") from e


# ---------- Produtos (M2) ----------

def listar_produtos(conn: sqlite3.Connection, busca: str = "") -> list:
    busca = (busca or "").strip()
    if busca:
        like = f"%{busca}%"
        cur = conn.execute(
            """SELECT p.*, f.nome_perfil FROM produtos p
               LEFT JOIN perfis_fiscais f ON f.id = p.id_perfil_fiscal
               WHERE p.nome LIKE ? OR p.codigo_interno LIKE ? OR p.ean LIKE ?
               ORDER BY p.nome""",
            (like, like, like),
        )
    else:
        cur = conn.execute(
            """SELECT p.*, f.nome_perfil FROM produtos p
               LEFT JOIN perfis_fiscais f ON f.id = p.id_perfil_fiscal
               ORDER BY p.nome"""
        )
    return [dict(r) for r in cur.fetchall()]


def obter_produto(conn: sqlite3.Connection, produto_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,))
    return _row_to_dict(cur.fetchone())


def criar_produto(conn: sqlite3.Connection, nome: str, preco_venda: float,
                  quantidade_estoque: float = 0, id_perfil_fiscal: int | None = None,
                  ean: str = "SEM GTIN", unidade_medida: str = "UN") -> dict:
    try:
        from services.codigo_interno import gerar_codigo_interno
    except ImportError:  # quando importado como src.database.repositories
        from src.services.codigo_interno import gerar_codigo_interno

    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome do produto é obrigatório.")
    if preco_venda is None or float(preco_venda) < 0:
        raise ValueError("Preço deve ser >= 0.")
    if float(quantidade_estoque) < 0:
        raise ValueError("Quantidade deve ser >= 0.")
    ean = (ean or "").strip() or "SEM GTIN"
    unidade_medida = (unidade_medida or "UN").strip().upper() or "UN"

    codigo = gerar_codigo_interno(conn)
    cur = conn.execute(
        """INSERT INTO produtos
           (nome, codigo_interno, ean, preco_venda, quantidade_estoque,
            unidade_medida, id_perfil_fiscal)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome, codigo, ean, float(preco_venda), float(quantidade_estoque),
         unidade_medida, id_perfil_fiscal),
    )
    conn.commit()
    return obter_produto(conn, cur.lastrowid)


def atualizar_produto(conn: sqlite3.Connection, produto_id: int, nome: str,
                       preco_venda: float, quantidade_estoque: float,
                       id_perfil_fiscal: int | None, ean: str = "SEM GTIN",
                       unidade_medida: str = "UN") -> None:
    if not (nome or "").strip():
        raise ValueError("Nome do produto é obrigatório.")
    if float(preco_venda) < 0 or float(quantidade_estoque) < 0:
        raise ValueError("Preço/quantidade devem ser >= 0.")
    conn.execute(
        """UPDATE produtos SET nome=?, ean=?, preco_venda=?, quantidade_estoque=?,
           unidade_medida=?, id_perfil_fiscal=? WHERE id=?""",
        (nome.strip(), (ean or "").strip() or "SEM GTIN", float(preco_venda),
         float(quantidade_estoque), (unidade_medida or "UN").strip().upper() or "UN",
         id_perfil_fiscal, produto_id),
    )
    conn.commit()


def excluir_produto(conn: sqlite3.Connection, produto_id: int) -> None:
    cur = conn.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError("Produto não encontrado.")


def aplicar_desconto(conn: sqlite3.Connection, produto_id: int, percentual: float) -> float:
    """Aplica desconto percentual (0-100) no preco_venda. Retorna novo preço."""
    percentual = float(percentual)
    if not (0 < percentual < 100):
        raise ValueError("Desconto deve estar entre 0 e 100 (exclusivo).")
    prod = obter_produto(conn, produto_id)
    if not prod:
        raise ValueError("Produto não encontrado.")
    novo = round(float(prod["preco_venda"]) * (1 - percentual / 100), 2)
    conn.execute("UPDATE produtos SET preco_venda=? WHERE id=?", (novo, produto_id))
    conn.commit()
    return novo


def buscar_para_pdv(conn: sqlite3.Connection, termo: str, limite: int = 20) -> list:
    """Autocomplete da frente de caixa: por nome ou código de 4 dígitos."""
    termo = (termo or "").strip()
    if not termo:
        cur = conn.execute(
            "SELECT * FROM produtos ORDER BY nome LIMIT ?", (limite,))
        return [dict(r) for r in cur.fetchall()]
    like = f"%{termo}%"
    cur = conn.execute(
        """SELECT * FROM produtos
           WHERE nome LIKE ? OR codigo_interno LIKE ?
           ORDER BY
             CASE WHEN codigo_interno = ? THEN 0 ELSE 1 END,
             nome LIMIT ?""",
        (like, like, termo, limite),
    )
    return [dict(r) for r in cur.fetchall()]


# ---------- Configurações (M1) ----------

def obter_config(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT * FROM configuracoes WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO configuracoes (id) VALUES (1)")
        conn.commit()
        return {"id": 1, "api_nfce_token": "", "api_nfce_url": "", "impressora_nome": ""}
    return dict(row)


def salvar_config(conn: sqlite3.Connection, api_nfce_token: str = "",
                  api_nfce_url: str = "", impressora_nome: str = "") -> None:
    conn.execute(
        """UPDATE configuracoes SET api_nfce_token=?, api_nfce_url=?, impressora_nome=?
           WHERE id=1""",
        ((api_nfce_token or "").strip(), (api_nfce_url or "").strip(),
         (impressora_nome or "").strip()),
    )
    conn.commit()
