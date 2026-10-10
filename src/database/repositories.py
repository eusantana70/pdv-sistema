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


# ---------- Caixa (M3) ----------

def obter_caixa_aberto(conn: sqlite3.Connection) -> dict | None:
    cur = conn.execute(
        "SELECT * FROM caixa_movimento WHERE status='aberto' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    return dict(row) if row else None


def listar_movimentos(conn: sqlite3.Connection, limite: int = 50) -> list:
    cur = conn.execute(
        "SELECT * FROM caixa_movimento ORDER BY id DESC LIMIT ?", (limite,))
    return [dict(r) for r in cur.fetchall()]


def abrir_caixa(conn: sqlite3.Connection, valor_inicial: float = 0) -> dict:
    from datetime import datetime
    if obter_caixa_aberto(conn):
        raise ValueError("Já existe um caixa aberto. Feche antes de abrir outro.")
    if float(valor_inicial) < 0:
        raise ValueError("Valor inicial deve ser >= 0.")
    agora = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO caixa_movimento (data_abertura, valor_inicial, status)"
        " VALUES (?, ?, 'aberto')",
        (agora, float(valor_inicial)),
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM caixa_movimento WHERE id=?", (cur.lastrowid,)).fetchone())


def fechar_caixa(conn: sqlite3.Connection, movimento_id: int, valor_final: float) -> None:
    from datetime import datetime
    if float(valor_final) < 0:
        raise ValueError("Valor final deve ser >= 0.")
    agora = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """UPDATE caixa_movimento SET data_fechamento=?, valor_final=?, status='fechado'
           WHERE id=? AND status='aberto'""",
        (agora, float(valor_final), movimento_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError("Caixa não encontrado ou já fechado.")


def adicionar_operacao(conn: sqlite3.Connection, id_movimento: int, tipo: str,
                       valor: float, observacao: str = "") -> int:
    from datetime import datetime
    if tipo not in ("sangria", "suprimento"):
        raise ValueError("Tipo deve ser sangria ou suprimento.")
    if float(valor) <= 0:
        raise ValueError("Valor deve ser maior que zero.")
    mov = conn.execute("SELECT * FROM caixa_movimento WHERE id=?", (id_movimento,)).fetchone()
    if not mov or mov["status"] != "aberto":
        raise ValueError("Operação exige um caixa aberto.")
    agora = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO caixa_operacoes (id_movimento, tipo, valor, data_hora, observacao)
           VALUES (?, ?, ?, ?, ?)""",
        (id_movimento, tipo, float(valor), agora, (observacao or "").strip()),
    )
    conn.commit()
    return cur.lastrowid


def listar_operacoes(conn: sqlite3.Connection, id_movimento: int) -> list:
    cur = conn.execute(
        "SELECT * FROM caixa_operacoes WHERE id_movimento=? ORDER BY id DESC",
        (id_movimento,))
    return [dict(r) for r in cur.fetchall()]


def saldo_previsto_caixa(conn: sqlite3.Connection, id_movimento: int) -> float:
    """valor_inicial + suprimentos - sangrias + vendas em dinheiro do movimento."""
    mov = conn.execute("SELECT * FROM caixa_movimento WHERE id=?", (id_movimento,)).fetchone()
    if not mov:
        raise ValueError("Movimento não encontrado.")
    saldo = float(mov["valor_inicial"] or 0)
    for op in listar_operacoes(conn, id_movimento):
        saldo += float(op["valor"]) if op["tipo"] == "suprimento" else -float(op["valor"])
    cur = conn.execute(
        """SELECT COALESCE(SUM(p.valor),0) AS t FROM vendas_pagamentos p
           JOIN vendas v ON v.id = p.id_venda
           WHERE v.id_movimento=? AND v.status='concluída' AND p.metodo='dinheiro'""",
        (id_movimento,))
    saldo += float(cur.fetchone()["t"])
    return round(saldo, 2)


# ---------- Vendas (M4; pagamento split entra no M5) ----------

def criar_venda(conn: sqlite3.Connection, id_movimento: int | None,
                itens: list, pagamentos: list) -> dict:
    """Cria venda, deduz estoque e registra pagamentos em transação única.

    itens: [{id_produto, quantidade, valor_unitario?}] (valor default = preco atual)
    pagamentos: [{metodo, valor, parcelas?}]
    """
    from datetime import datetime
    if not itens:
        raise ValueError("Venda sem itens.")
    mov = None
    if id_movimento is not None:
        mov = conn.execute("SELECT * FROM caixa_movimento WHERE id=?",
                           (id_movimento,)).fetchone()
        if not mov or mov["status"] != "aberto":
            raise ValueError("Só é possível vender com caixa aberto.")
    total_itens = 0.0
    linhas = []
    for it in itens:
        qtd = float(it.get("quantidade", 0))
        if qtd <= 0:
            raise ValueError("Quantidade deve ser > 0.")
        prod = conn.execute("SELECT * FROM produtos WHERE id=?",
                            (it["id_produto"],)).fetchone()
        if not prod:
            raise ValueError("Produto não encontrado.")
        if float(prod["quantidade_estoque"]) < qtd:
            raise ValueError(f'Estoque insuficiente: {prod["nome"]} '
                             f'(tem {prod["quantidade_estoque"]:g}).')
        vu = float(it.get("valor_unitario", prod["preco_venda"]))
        if vu < 0:
            raise ValueError("Valor unitário deve ser >= 0.")
        sub = round(qtd * vu, 2)
        total_itens = round(total_itens + sub, 2)
        linhas.append({"id_produto": prod["id"], "quantidade": qtd,
                        "valor_unitario": vu, "subtotal": sub})
    total_pago = round(sum(float(p.get("valor", 0)) for p in pagamentos), 2)
    if not pagamentos or total_pago < total_itens:
        raise ValueError(f"Pagamento insuficiente: total R$ {total_itens:.2f}, "
                         f"recebido R$ {total_pago:.2f}.")
    for p in pagamentos:
        if p.get("metodo") not in ("dinheiro", "credito", "debito", "pix"):
            raise ValueError("Método inválido.")
        if float(p.get("valor", 0)) <= 0:
            raise ValueError("Valor do pagamento deve ser > 0.")
        if p.get("metodo") == "credito" and not (1 <= int(p.get("parcelas", 1)) <= 12):
            raise ValueError("Parcelas do crédito: 1 a 12.")
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        cur = conn.execute(
            """INSERT INTO vendas (id_movimento, total, data_hora, status, nfe_status)
               VALUES (?, ?, ?, 'concluída', 'pendente')""",
            (id_movimento, total_itens, agora),
        )
        venda_id = cur.lastrowid
        for ln in linhas:
            conn.execute(
                """INSERT INTO vendas_itens (id_venda, id_produto, quantidade,
                   valor_unitario, subtotal) VALUES (?, ?, ?, ?, ?)""",
                (venda_id, ln["id_produto"], ln["quantidade"],
                 ln["valor_unitario"], ln["subtotal"]),
            )
            conn.execute(
                "UPDATE produtos SET quantidade_estoque = quantidade_estoque - ? WHERE id=?",
                (ln["quantidade"], ln["id_produto"]),
            )
        for p in pagamentos:
            conn.execute(
                "INSERT INTO vendas_pagamentos (id_venda, metodo, valor, parcelas)"
                " VALUES (?, ?, ?, ?)",
                (venda_id, p["metodo"], float(p["valor"]),
                 int(p.get("parcelas", 1)) if p["metodo"] == "credito" else 1),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return dict(conn.execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone())


# ---------- Vendas: leitura fiscal / impressão (M6) ----------

def obter_venda(conn: sqlite3.Connection, venda_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM vendas WHERE id=?", (venda_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def listar_itens_venda(conn: sqlite3.Connection, venda_id: int) -> list:
    cur = conn.execute(
        """SELECT i.*, p.nome, p.codigo_interno, p.id_perfil_fiscal, p.unidade_medida
           FROM vendas_itens i LEFT JOIN produtos p ON p.id = i.id_produto
           WHERE i.id_venda=? ORDER BY i.id""",
        (venda_id,))
    return [dict(r) for r in cur.fetchall()]


def listar_pagamentos_venda(conn: sqlite3.Connection, venda_id: int) -> list:
    cur = conn.execute(
        "SELECT * FROM vendas_pagamentos WHERE id_venda=? ORDER BY id", (venda_id,))
    return [dict(r) for r in cur.fetchall()]


def atualizar_nfe(conn: sqlite3.Connection, venda_id: int, status: str,
                  link: str = "", xml: str = "") -> None:
    conn.execute(
        "UPDATE vendas SET nfe_status=?, nfe_link_cupom=?, nfe_xml=? WHERE id=?",
        (status, link or "", xml or "", venda_id),
    )
    conn.commit()
