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
                  ean: str = "SEM GTIN", unidade_medida: str = "UN",
                  categoria: str = "Alimentos", cor: str = "green",
                  validade: str = "") -> dict:
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
    ean = (ean or "").strip()
    if not ean or ean.upper() == "SEM GTIN":
        # código opcional: gera EAN aleatório único (8 dígitos) sem conflito
        import random
        for _ in range(9000):
            cand = f"{random.randint(10000000, 99999999)}"
            if conn.execute("SELECT 1 FROM produtos WHERE ean = ?", (cand,)).fetchone() is None:
                ean = cand
                break
        else:
            ean = "SEM GTIN"
    unidade_medida = (unidade_medida or "UN").strip().upper() or "UN"
    categoria = (categoria or "Alimentos").strip() or "Alimentos"
    cor = (cor or "green").strip() or "green"
    validade = (validade or "").strip()  # "" = validade indeterminada

    # garante colunas novas em bancos antigos
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    try:
        migrate(conn)
    except Exception:
        pass

    codigo = gerar_codigo_interno(conn)
    cur = conn.execute(
        """INSERT INTO produtos
           (nome, codigo_interno, ean, preco_venda, quantidade_estoque,
            unidade_medida, id_perfil_fiscal, categoria, cor, validade)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, codigo, ean, float(preco_venda), float(quantidade_estoque),
         unidade_medida, id_perfil_fiscal, categoria, cor, validade),
    )
    conn.commit()
    return obter_produto(conn, cur.lastrowid)


def atualizar_produto(conn: sqlite3.Connection, produto_id: int, nome: str,
                       preco_venda: float, quantidade_estoque: float,
                       id_perfil_fiscal: int | None, ean: str = "SEM GTIN",
                       unidade_medida: str = "UN", categoria: str | None = None,
                       cor: str | None = None, validade: str | None = None) -> None:
    if not (nome or "").strip():
        raise ValueError("Nome do produto é obrigatório.")
    if float(preco_venda) < 0 or float(quantidade_estoque) < 0:
        raise ValueError("Preço/quantidade devem ser >= 0.")
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    try:
        migrate(conn)
    except Exception:
        pass
    sets = ["nome=?", "ean=?", "preco_venda=?", "quantidade_estoque=?",
            "unidade_medida=?", "id_perfil_fiscal=?"]
    vals: list = [nome.strip(), (ean or "").strip() or "SEM GTIN", float(preco_venda),
         float(quantidade_estoque), (unidade_medida or "UN").strip().upper() or "UN",
         id_perfil_fiscal]
    if categoria is not None:
        sets.append("categoria=?")
        vals.append((categoria or "Alimentos").strip() or "Alimentos")
    if cor is not None:
        sets.append("cor=?")
        vals.append((cor or "green").strip() or "green")
    if validade is not None:
        sets.append("validade=?")
        vals.append((validade or "").strip())
    vals.append(produto_id)
    conn.execute(f"UPDATE produtos SET {', '.join(sets)} WHERE id=?", vals)
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


def obter_ultimo_fechado(conn: sqlite3.Connection) -> dict | None:
    """Último movimento fechado (para exibir quando o caixa está fechado)."""
    cur = conn.execute(
        "SELECT * FROM caixa_movimento WHERE status='fechado'"
        " ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    return dict(row) if row else None


def listar_operacoes_dia(conn: sqlite3.Connection, dia: str = "",
                         limite: int = 200) -> list:
    """Sangrias/suprimentos do dia (dia='YYYY-MM-DD'; vazio = todos)."""
    sql = ("SELECT o.*, m.data_abertura FROM caixa_operacoes o"
           " JOIN caixa_movimento m ON m.id = o.id_movimento WHERE 1=1")
    params: list = []
    if dia:
        sql += " AND substr(o.data_hora, 1, 10) = ?"
        params.append(dia)
    sql += " ORDER BY o.id DESC LIMIT ?"
    params.append(limite)
    cur = conn.execute(sql, params)
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
                itens: list, pagamentos: list, desconto_percentual: float = 0) -> dict:
    """Cria venda, deduz estoque e registra pagamentos em transação única.

    itens: [{id_produto, quantidade, valor_unitario?}] (valor default = preco atual)
    pagamentos: [{metodo, valor, parcelas?}]
    desconto_percentual: 0-100 aplicado sobre o subtotal (F3 do front Lumina).
    """
    from datetime import datetime
    if not itens:
        raise ValueError("Venda sem itens.")
    desconto_percentual = float(desconto_percentual or 0)
    if not (0 <= desconto_percentual < 100):
        raise ValueError("Desconto deve estar entre 0 e 100.")
    mov = None
    if id_movimento is not None:
        mov = conn.execute("SELECT * FROM caixa_movimento WHERE id=?",
                           (id_movimento,)).fetchone()
        if not mov or mov["status"] != "aberto":
            raise ValueError("Só é possível vender com caixa aberto.")
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    try:
        migrate(conn)
    except Exception:
        pass
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
        # valor_unitario chega como None quando a tela nao sobrescreve o preco
        # (o Pydantic devolve a chave com None, entao .get(chave, padrao) nao
        # funciona aqui — sem este "is not None" toda venda quebrava com 500)
        vu_enviado = it.get("valor_unitario")
        vu = float(vu_enviado) if vu_enviado is not None else float(prod["preco_venda"])
        if vu < 0:
            raise ValueError("Valor unitário deve ser >= 0.")
        sub = round(qtd * vu, 2)
        total_itens = round(total_itens + sub, 2)
        linhas.append({"id_produto": prod["id"], "quantidade": qtd,
                        "valor_unitario": vu, "subtotal": sub})
    total_pago = round(sum(float(p.get("valor", 0)) for p in pagamentos), 2)
    total_final = round(total_itens * (1 - desconto_percentual / 100), 2)
    if not pagamentos or total_pago < total_final:
        raise ValueError(f"Pagamento insuficiente: total R$ {total_final:.2f}, "
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
            """INSERT INTO vendas (id_movimento, total, data_hora, status, nfe_status,
               desconto_percentual)
               VALUES (?, ?, ?, 'concluída', 'pendente', ?)""",
            (id_movimento, total_final, agora, desconto_percentual),
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
            try:
                deduzir_lotes_fifo(conn, ln["id_produto"], ln["quantidade"])
            except Exception:
                pass
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


# ---------- Histórico e relatórios (M7) ----------

def listar_vendas(conn: sqlite3.Connection, dia: str = "", status: str = "",
                  limite: int = 200) -> list:
    """Lista vendas. dia='YYYY-MM-DD' filtra por data; status filtra concluída/cancelada."""
    sql = "SELECT * FROM vendas WHERE 1=1"
    params: list = []
    if dia:
        sql += " AND substr(data_hora, 1, 10) = ?"
        params.append(dia)
    if status in ("concluída", "cancelada"):
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limite)
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def cancelar_venda(conn: sqlite3.Connection, venda_id: int) -> None:
    """Cancela venda: status=cancelada, estorna estoque, nfe_status=cancelado.

    O comando de cancelamento para a API é enviado pelo worker fiscal (M6);
    aqui só marcamos — a venda continua no histórico.
    """
    venda = conn.execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise ValueError("Venda não encontrada.")
    if venda["status"] == "cancelada":
        raise ValueError("Venda já cancelada.")
    try:
        itens = conn.execute(
            "SELECT * FROM vendas_itens WHERE id_venda=?", (venda_id,)).fetchall()
        for it in itens:
            if it["id_produto"] is not None:
                conn.execute(
                    "UPDATE produtos SET quantidade_estoque = quantidade_estoque + ?"
                    " WHERE id=?",
                    (it["quantidade"], it["id_produto"]),
                )
                try:  # devolve ao lote mais próximo (contabilidade de validade)
                    lotes = conn.execute(
                        "SELECT * FROM produto_lotes WHERE id_produto=? ORDER BY validade",
                        (it["id_produto"],)).fetchall()
                    if lotes:
                        conn.execute(
                            "UPDATE produto_lotes SET quantidade = quantidade + ? WHERE id=?",
                            (it["quantidade"], lotes[0]["id"]),
                        )
                except Exception:
                    pass
        conn.execute("UPDATE vendas SET status='cancelada' WHERE id=?", (venda_id,))
        conn.execute(
            "UPDATE vendas SET nfe_status='cancelado' WHERE id=? AND nfe_status='autorizado'",
            (venda_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def resumo_limpeza(conn: sqlite3.Connection, inicio: str = "", fim: str = "") -> dict:
    """Prévia da limpeza: quantas vendas e total no intervalo (vazio = tudo)."""
    sql = "SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS t FROM vendas WHERE 1=1"
    params: list = []
    if inicio:
        sql += " AND substr(data_hora,1,10) >= ?"
        params.append(inicio)
    if fim:
        sql += " AND substr(data_hora,1,10) <= ?"
        params.append(fim)
    row = conn.execute(sql, params).fetchone()
    return {"vendas": row["n"], "total": round(float(row["t"] or 0), 2),
            "inicio": inicio or "início", "fim": fim or "fim"}


def limpar_vendas(conn: sqlite3.Connection, inicio: str = "", fim: str = "") -> dict:
    """Apaga vendas do histórico no intervalo (vazio = todo o período).

    Estorna o estoque das concluídas antes de apagar (itens/pagamentos saem
    por CASCADE). Canceladas só são apagadas (estoque já estornado no cancelamento).
    """
    sql = "SELECT * FROM vendas WHERE 1=1"
    params: list = []
    if inicio:
        sql += " AND substr(data_hora,1,10) >= ?"
        params.append(inicio)
    if fim:
        sql += " AND substr(data_hora,1,10) <= ?"
        params.append(fim)
    vendas = conn.execute(sql, params).fetchall()
    try:
        removidas = 0
        total = 0.0
        for venda in vendas:
            if venda["status"] == "concluída":
                itens = conn.execute(
                    "SELECT * FROM vendas_itens WHERE id_venda=?", (venda["id"],)).fetchall()
                for it in itens:
                    if it["id_produto"] is not None:
                        conn.execute(
                            "UPDATE produtos SET quantidade_estoque = quantidade_estoque + ?"
                            " WHERE id=?",
                            (it["quantidade"], it["id_produto"]),
                        )
                        try:
                            lotes = conn.execute(
                                "SELECT * FROM produto_lotes WHERE id_produto=? ORDER BY validade",
                                (it["id_produto"],)).fetchall()
                            if lotes:
                                conn.execute(
                                    "UPDATE produto_lotes SET quantidade = quantidade + ? WHERE id=?",
                                    (it["quantidade"], lotes[0]["id"]),
                                )
                        except Exception:
                            pass
            total = round(total + float(venda["total"] or 0), 2)
            conn.execute("DELETE FROM vendas WHERE id=?", (venda["id"],))
            removidas += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"removidas": removidas, "total": total}


def totais_por_pagamento(conn: sqlite3.Connection, dia: str) -> dict:
    """Totais do dia por método (só concluídas). Retorna {metodo: total} + _geral."""
    cur = conn.execute(
        """SELECT p.metodo AS metodo, COALESCE(SUM(p.valor),0) AS total
           FROM vendas_pagamentos p JOIN vendas v ON v.id = p.id_venda
           WHERE v.status='concluída' AND substr(v.data_hora,1,10)=?
           GROUP BY p.metodo""",
        (dia,))
    out = {"dinheiro": 0.0, "credito": 0.0, "debito": 0.0, "pix": 0.0}
    for r in cur.fetchall():
        out[r["metodo"]] = round(float(r["total"]), 2)
    out["_geral"] = round(sum(v for k, v in out.items() if not k.startswith("_")), 2)
    cur2 = conn.execute(
        """SELECT COUNT(*) AS n FROM vendas
           WHERE status='concluída' AND substr(data_hora,1,10)=?""",
        (dia,))
    out["_vendas"] = cur2.fetchone()["n"]
    return out


# ---------- Relatório detalhado (com filtros) ----------

FILTROS_ROTULOS = {
    "dinheiro": "Dinheiro", "credito": "Crédito", "debito": "Débito", "pix": "PIX",
}


def _condicoes(inicio: str, fim: str, categorias: list[str], produtos: list[str],
               formas: list[str], incluir_canceladas: bool = False) -> tuple[str, list]:
    """Condições de data/produto (sem join de pagamento — evita duplicar linhas)."""
    sql = " WHERE 1=1"
    params: list = []
    if inicio:
        sql += " AND substr(v.data_hora,1,10) >= ?"
        params.append(inicio)
    if fim:
        sql += " AND substr(v.data_hora,1,10) <= ?"
        params.append(fim)
    if not incluir_canceladas:
        sql += " AND v.status='concluída'"
    if formas:
        # vendas que têm ao menos um pagamento da forma escolhida
        sql += (f" AND v.id IN (SELECT id_venda FROM vendas_pagamentos "
                f"WHERE metodo IN ({','.join('?' * len(formas))}))")
        params.extend(formas)
    if categorias:
        sql += (f" AND EXISTS (SELECT 1 FROM vendas_itens vi JOIN produtos vp ON vp.id=vi.id_produto "
                f"WHERE vi.id_venda=v.id AND vp.categoria IN ({','.join('?' * len(categorias))}))")
        params.extend(categorias)
    if produtos:
        sql += (f" AND EXISTS (SELECT 1 FROM vendas_itens vi JOIN produtos vp ON vp.id=vi.id_produto "
                f"WHERE vi.id_venda=v.id AND vp.nome LIKE ({','.join('?' * len(produtos))}))")
        params.extend([f"%{p}%" for p in produtos])
    return sql, params


def relatorio_detalhado(conn: sqlite3.Connection, inicio: str, fim: str,
                        formas: list[str] | None = None,
                        categorias: list[str] | None = None,
                        produtos: list[str] | None = None,
                        agrupar: str = "dia",
                        limite_produtos: int = 15) -> dict:
    """Dataset completo do relatório com filtros (data, forma de pagamento, produto).

    Consultas separadas de pagamento e de itens: juntar as duas tabelas numa só
    consulta multiplica as linhas e infla os totais.
    """
    formas = [f for f in (formas or []) if f in FILTROS_ROTULOS]
    categorias = [c for c in (categorias or []) if c]
    produtos = [p for p in (produtos or []) if p]
    where, params = _condicoes(inicio, fim, categorias, produtos, formas)

    # ---- serie temporal (por pagamento) ----
    grupo = "substr(v.data_hora,12,2)" if agrupar == "hora" else "substr(v.data_hora,1,10)"
    cur = conn.execute(
        f"""SELECT {grupo} AS k,
                   COUNT(DISTINCT v.id) AS vendas,
                   COALESCE(SUM(p.valor),0) AS total,
                   COALESCE(SUM(CASE WHEN p.metodo='dinheiro' THEN p.valor ELSE 0 END),0) AS dinheiro,
                   COALESCE(SUM(CASE WHEN p.metodo='credito' THEN p.valor ELSE 0 END),0) AS credito,
                   COALESCE(SUM(CASE WHEN p.metodo='debito'  THEN p.valor ELSE 0 END),0) AS debito,
                   COALESCE(SUM(CASE WHEN p.metodo='pix'     THEN p.valor ELSE 0 END),0) AS pix
            FROM vendas v JOIN vendas_pagamentos p ON p.id_venda = v.id
            {where} GROUP BY k ORDER BY k""", params)
    serie = [{"rotulo": r["k"], "vendas": int(r["vendas"]),
              **{k: round(float(r[k]), 2) for k in ("total", "dinheiro", "credito", "debito", "pix")}}
             for r in cur.fetchall()]

    # ---- por forma de pagamento ----
    cur = conn.execute(
        f"""SELECT p.metodo AS forma, COUNT(DISTINCT v.id) AS vendas,
                   COALESCE(SUM(p.valor),0) AS total
            FROM vendas v JOIN vendas_pagamentos p ON p.id_venda = v.id
            {where} GROUP BY p.metodo ORDER BY total DESC""", params)
    por_forma = [{"forma": r["forma"], "rotulo": FILTROS_ROTULOS.get(r["forma"], r["forma"].title()),
                  "vendas": int(r["vendas"]), "total": round(float(r["total"]), 2)}
                 for r in cur.fetchall() if r["forma"]]

    # ---- por produto / categoria (por itens) ----
    base_itens = ("FROM vendas v JOIN vendas_itens i ON i.id_venda = v.id "
                  "LEFT JOIN produtos pr ON pr.id = i.id_produto ")
    cur = conn.execute(
        f"""SELECT COALESCE(pr.nome,'(produto removido)') AS nome,
                   COALESCE(pr.categoria,'') AS categoria,
                   COALESCE(SUM(i.quantidade),0) AS qtd,
                   COALESCE(SUM(i.subtotal),0) AS total
            {base_itens}{where}
            GROUP BY nome ORDER BY total DESC LIMIT ?""", params + [limite_produtos])
    por_produto = [{"nome": r["nome"], "categoria": r["categoria"],
                    "quantidade": round(float(r["qtd"]), 2),
                    "total": round(float(r["total"]), 2)} for r in cur.fetchall()]

    cur = conn.execute(
        f"""SELECT COALESCE(NULLIF(pr.categoria,''),'Sem categoria') AS categoria,
                   COALESCE(SUM(i.quantidade),0) AS qtd,
                   COALESCE(SUM(i.subtotal),0) AS total
            {base_itens}{where}
            GROUP BY categoria ORDER BY total DESC""", params)
    por_categoria = [{"categoria": r["categoria"], "quantidade": round(float(r["qtd"]), 2),
                      "total": round(float(r["total"]), 2)} for r in cur.fetchall()]

    total = round(sum(s["total"] for s in serie), 2)
    vendas = sum(s["vendas"] for s in serie)
    itens = sum(p["quantidade"] for p in por_produto)
    # desconto médio: usa o período (filtros de pagamento/produto não se aplicam a média)
    desconto_medio = 0.0
    try:
        sql_d = "SELECT COALESCE(AVG(v.desconto_percentual),0) AS d FROM vendas v WHERE 1=1"
        p_d: list = []
        if inicio:
            sql_d += " AND substr(v.data_hora,1,10) >= ?"
            p_d.append(inicio)
        if fim:
            sql_d += " AND substr(v.data_hora,1,10) <= ?"
            p_d.append(fim)
        if not incluir_canceladas:
            sql_d += " AND v.status='concluída'"
        desconto_medio = round(float(conn.execute(sql_d, p_d).fetchone()["d"]), 2)
    except Exception:
        desconto_medio = 0.0
    return {
        "inicio": inicio, "fim": fim,
        "filtros": {"formas": formas, "categorias": categorias, "produtos": produtos},
        "resumo": {
            "total": total,
            "vendas": vendas,
            "itens": round(itens, 2),
            "ticket_medio": round(total / vendas, 2) if vendas else 0.0,
            "desconto_medio": desconto_medio,
            "formas": len(por_forma),
            "produtos": len(por_produto),
        },
        "serie": serie,
        "por_forma": por_forma,
        "por_produto": por_produto,
        "por_categoria": por_categoria,
    }


# ---------- Lotes de validade (parciais por produto) ----------

def listar_lotes(conn: sqlite3.Connection, id_produto: int) -> list:
    cur = conn.execute(
        "SELECT * FROM produto_lotes WHERE id_produto=? ORDER BY validade",
        (id_produto,))
    return [dict(r) for r in cur.fetchall()]


def _validar_validade(validade: str) -> str:
    v = (validade or "").strip()
    if not v:
        raise ValueError("Validade é obrigatória no lote (use remover p/ indeterminada).")
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("Validade deve estar no formato AAAA-MM-DD.")
    return v


def adicionar_lote(conn: sqlite3.Connection, id_produto: int,
                   validade: str, quantidade: float) -> dict:
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    migrate(conn)
    if not conn.execute("SELECT 1 FROM produtos WHERE id=?", (id_produto,)).fetchone():
        raise ValueError("Produto não encontrado.")
    v = _validar_validade(validade)
    if float(quantidade) <= 0:
        raise ValueError("Quantidade do lote deve ser > 0.")
    cur = conn.execute(
        "INSERT INTO produto_lotes (id_produto, validade, quantidade) VALUES (?, ?, ?)",
        (id_produto, v, float(quantidade)),
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM produto_lotes WHERE id=?", (cur.lastrowid,)).fetchone())


def remover_lote(conn: sqlite3.Connection, lote_id: int) -> None:
    cur = conn.execute("DELETE FROM produto_lotes WHERE id=?", (lote_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError("Lote não encontrado.")


def substituir_lotes(conn: sqlite3.Connection, id_produto: int, lotes: list) -> list:
    """Troca todos os lotes do produto. lotes=[{validade, quantidade}]."""
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    migrate(conn)
    if not conn.execute("SELECT 1 FROM produtos WHERE id=?", (id_produto,)).fetchone():
        raise ValueError("Produto não encontrado.")
    try:
        conn.execute("DELETE FROM produto_lotes WHERE id_produto=?", (id_produto,))
        for lote in (lotes or []):
            v = _validar_validade(str(lote.get("validade", "")))
            qtd = float(lote.get("quantidade", 0))
            if qtd <= 0:
                raise ValueError("Quantidade do lote deve ser > 0.")
            conn.execute(
                "INSERT INTO produto_lotes (id_produto, validade, quantidade)"
                " VALUES (?, ?, ?)",
                (id_produto, v, qtd),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return listar_lotes(conn, id_produto)


def deduzir_lotes_fifo(conn: sqlite3.Connection, id_produto: int, quantidade: float) -> None:
    """Baixa a venda dos lotes com vencimento mais próximo primeiro (FIFO)."""
    restante = float(quantidade)
    lotes = conn.execute(
        "SELECT * FROM produto_lotes WHERE id_produto=? ORDER BY validade",
        (id_produto,)).fetchall()
    for lote in lotes:
        if restante <= 0:
            break
        usa = min(float(lote["quantidade"]), restante)
        nova = round(float(lote["quantidade"]) - usa, 3)
        if nova <= 0:
            conn.execute("DELETE FROM produto_lotes WHERE id=?", (lote["id"],))
        else:
            conn.execute("UPDATE produto_lotes SET quantidade=? WHERE id=?",
                         (nova, lote["id"]))
        restante = round(restante - usa, 3)


# ---------- Config completa (front Lumina: empresa + fiscal multi-provedor) ----------

CONFIG_FULL_DEFAULTS: dict = {
    "fiscal_provider": "mock",
    "ambiente": "homologacao",
    "modelo_doc": "NFC-e",
    "serie": "1",
    "proximo_numero": 1,
    "razao_social": "",
    "nome_fantasia": "",
    "cnpj": "",
    "ie": "",
    "email": "",
    "telefone": "",
    "endereco": "",
    "cidade_uf": "",
    "cep": "",
    "impressora_nome": "",
    "impressora_largura": "80mm",
    "impressora_vias": 1,
    "auto_print": 1,
    "exibir_logo": 1,
    "corte_auto": 1,
    "mock_url": "http://localhost:3000",
    "nuvem_token": "",
    "nuvem_url": "https://api.nuvemfiscal.com.br/nfce",
    "focus_token": "",
    "focus_url": "https://api.focusnfe.com.br/v2/nfce",
    "custom_token": "",
    "custom_url": "",
    "sefaz_cert_path": "",
    "sefaz_cert_senha": "",
    "desconto_tipo": "nenhum",
    "desconto_valor": 0,
    "api_nfce_token": "",
    "api_nfce_url": "",
    # ---- nota NÃO fiscal (comprovante impresso) ----
    "recibo_titulo": "",
    "recibo_subtitulo": "Cupom de venda - sem valor fiscal",
    "recibo_rodape": "Obrigado pela preferencia!",
    "recibo_largura": "48",
    "recibo_mostrar_cnpj": 1,
    "recibo_mostrar_itens": 1,
    "recibo_mostrar_pagamentos": 1,
    "recibo_mostrar_troco": 1,
    "recibo_mostrar_atendente": 0,
    "recibo_mostrar_qrcode": 1,
    "imprimir_cupom_fiscal": 1,
    "imprimir_cupom_nao_fiscal": 1,
    "recibo_qrcode_link": "",
    "recibo_tributos_federal": 0,
    "recibo_tributos_estadual": 0,
    "recibo_aviso_trocas": "Trocas somente mediante notinha",
    "recibo_mostrar_tributos": 1,
    "recibo_mostrar_aviso_trocas": 1,
}


def obter_config_full(conn: sqlite3.Connection) -> dict:
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    try:
        migrate(conn)
    except Exception:
        pass
    cur = conn.execute("SELECT * FROM configuracoes WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO configuracoes (id) VALUES (1)")
        conn.commit()
        return {"id": 1, **CONFIG_FULL_DEFAULTS}
    d = dict(row)
    for k, v in CONFIG_FULL_DEFAULTS.items():
        d.setdefault(k, v)
        if d[k] is None:
            d[k] = v
    return d


def salvar_config_full(conn: sqlite3.Connection, dados: dict) -> dict:
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    migrate(conn)
    atual = obter_config_full(conn)
    merged = {**atual, **{k: v for k, v in (dados or {}).items()
                          if k in CONFIG_FULL_DEFAULTS}}
    # espelho legacy: custom <-> api_nfce_*
    if merged.get("custom_url") and not merged.get("api_nfce_url"):
        merged["api_nfce_url"] = merged["custom_url"]
    if merged.get("custom_token") and not merged.get("api_nfce_token"):
        merged["api_nfce_token"] = merged["custom_token"]
    if merged.get("api_nfce_url") and not merged.get("custom_url"):
        merged["custom_url"] = merged["api_nfce_url"]
    if merged.get("api_nfce_token") and not merged.get("custom_token"):
        merged["custom_token"] = merged["api_nfce_token"]
    cols = list(CONFIG_FULL_DEFAULTS.keys()) + ["api_nfce_token", "api_nfce_url"]
    sets = ", ".join(f"{c}=?" for c in cols)
    vals = [merged.get(c, "") for c in cols] + [1]
    conn.execute(f"UPDATE configuracoes SET {sets} WHERE id=?", vals)
    conn.commit()
    return obter_config_full(conn)


# ---------- Usuários e sessões ----------

def _hash(senha: str) -> str:
    try:
        from services.permissoes import hash_senha
    except ImportError:
        from src.services.permissoes import hash_senha
    return hash_senha(senha)


def listar_usuarios(conn: sqlite3.Connection, incluir_inativos: bool = True) -> list:
    sql = "SELECT id, nome, login, perfil, ativo, criado_em FROM usuarios"
    if not incluir_inativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY nome"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def obter_usuario(conn: sqlite3.Connection, usuario_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, nome, login, perfil, ativo, criado_em FROM usuarios WHERE id=?",
        (usuario_id,)).fetchone()
    return dict(row) if row else None


def criar_usuario(conn: sqlite3.Connection, nome: str, login: str,
                  senha: str, perfil: str = "operador") -> dict:
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    migrate(conn)
    nome = (nome or "").strip()
    login = (login or "").strip().lower()
    if not nome:
        raise ValueError("Nome é obrigatório.")
    if not login or " " in login:
        raise ValueError("Login obrigatório (sem espaços).")
    if not senha or len(senha) < 4:
        raise ValueError("Senha deve ter ao menos 4 caracteres.")
    if perfil not in ("admin", "operador"):
        raise ValueError("Perfil deve ser admin ou operador.")
    if conn.execute("SELECT 1 FROM usuarios WHERE login=?", (login,)).fetchone():
        raise ValueError("Login já cadastrado.")
    from datetime import datetime
    cur = conn.execute(
        """INSERT INTO usuarios (nome, login, senha_hash, perfil, ativo, criado_em)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (nome, login, _hash(senha), perfil, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return obter_usuario(conn, cur.lastrowid)


def atualizar_usuario(conn: sqlite3.Connection, usuario_id: int, nome: str,
                      perfil: str, ativo: int = 1, senha: str = "") -> dict:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome é obrigatório.")
    if perfil not in ("admin", "operador"):
        raise ValueError("Perfil deve ser admin ou operador.")
    usr = obter_usuario(conn, usuario_id)
    if not usr:
        raise ValueError("Usuário não encontrado.")
    if perfil != "admin" and ativo:
        # não pode ficar sem nenhum admin ativo
        admins = [u for u in listar_usuarios(conn)
                  if u["perfil"] == "admin" and u["ativo"] and u["id"] != usuario_id]
        if usr["perfil"] == "admin" and not admins:
            raise ValueError("É preciso manter ao menos um administrador ativo.")
    if senha:
        conn.execute("UPDATE usuarios SET nome=?, perfil=?, ativo=?, senha_hash=? WHERE id=?",
                     (nome, perfil, 1 if ativo else 0, _hash(senha), usuario_id))
    else:
        conn.execute("UPDATE usuarios SET nome=?, perfil=?, ativo=? WHERE id=?",
                     (nome, perfil, 1 if ativo else 0, usuario_id))
    if not ativo:
        conn.execute("DELETE FROM sessoes WHERE id_usuario=?", (usuario_id,))
    conn.commit()
    return obter_usuario(conn, usuario_id)


def excluir_usuario(conn: sqlite3.Connection, usuario_id: int) -> None:
    usr = obter_usuario(conn, usuario_id)
    if not usr:
        raise ValueError("Usuário não encontrado.")
    if usr["perfil"] == "admin":
        admins = [u for u in listar_usuarios(conn)
                  if u["perfil"] == "admin" and u["ativo"] and u["id"] != usuario_id]
        if not admins:
            raise ValueError("É preciso manter ao menos um administrador ativo.")
    conn.execute("DELETE FROM sessoes WHERE id_usuario=?", (usuario_id,))
    cur = conn.execute("DELETE FROM usuarios WHERE id=?", (usuario_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError("Usuário não encontrado.")


def autenticar(conn: sqlite3.Connection, login: str, senha: str) -> dict | None:
    import sys
    SRC = str(__import__("pathlib").Path(__file__).resolve().parents[1])
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    try:
        from services.permissoes import conferir_senha
    except ImportError:
        from src.services.permissoes import conferir_senha
    row = conn.execute("SELECT * FROM usuarios WHERE login=?", ((login or "").strip().lower(),)).fetchone()
    if not row or not row["ativo"]:
        return None
    if not conferir_senha(senha, row["senha_hash"]):
        return None
    return {"id": row["id"], "nome": row["nome"], "login": row["login"],
            "perfil": row["perfil"], "ativo": row["ativo"]}


def criar_sessao(conn: sqlite3.Connection, usuario_id: int, horas: int = 12) -> str:
    import secrets
    from datetime import datetime, timedelta
    agora = datetime.now()
    token = secrets.token_hex(24)
    conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora.isoformat(timespec="seconds"),))
    conn.execute(
        "INSERT INTO sessoes (token, id_usuario, criado_em, expira_em) VALUES (?, ?, ?, ?)",
        (token, usuario_id, agora.isoformat(timespec="seconds"),
         (agora + timedelta(hours=max(1, int(horas or 12)))).isoformat(timespec="seconds")),
    )
    conn.commit()
    return token


def usuario_do_token(conn: sqlite3.Connection, token: str) -> dict | None:
    if not token:
        return None
    from datetime import datetime
    row = conn.execute(
        """SELECT u.id, u.nome, u.login, u.perfil, u.ativo, s.expira_em
           FROM sessoes s JOIN usuarios u ON u.id = s.id_usuario
           WHERE s.token = ?""", (token,)).fetchone()
    if not row:
        return None
    if row["expira_em"] < datetime.now().isoformat(timespec="seconds"):
        conn.execute("DELETE FROM sessoes WHERE token=?", (token,))
        conn.commit()
        return None
    if not row["ativo"]:
        return None
    return {"id": row["id"], "nome": row["nome"], "login": row["login"], "perfil": row["perfil"]}


def encerrar_sessao(conn: sqlite3.Connection, token: str) -> None:
    if token:
        conn.execute("DELETE FROM sessoes WHERE token=?", (token,))
        conn.commit()


def limpar_sessoes_expiradas(conn: sqlite3.Connection) -> None:
    from datetime import datetime
    conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (datetime.now().isoformat(timespec="seconds"),))
    conn.commit()


def resetar_usuarios(conn: sqlite3.Connection, nome: str = "Administrador",
                     login: str = "admin", senha: str = "admin123",
                     perfil: str = "admin") -> dict:
    """Apaga todas as pessoas/sessões e recria um acesso padrão."""
    from datetime import datetime
    try:
        from database.migrate import migrate
    except ImportError:
        from src.database.migrate import migrate
    migrate(conn)  # garante tabelas (e semeia admin se estiver vazio)
    conn.execute("DELETE FROM sessoes")
    conn.execute("DELETE FROM usuarios")
    login = (login or "admin").strip().lower()
    cur = conn.execute(
        """INSERT INTO usuarios (nome, login, senha_hash, perfil, ativo, criado_em)
           VALUES (?, ?, ?, ?, 1, ?)""",
        ((nome or "Administrador").strip(), login, _hash(senha or "admin123"),
         perfil if perfil in ("admin", "operador") else "admin",
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return obter_usuario(conn, cur.lastrowid)


def produto_para_front(p: dict, lotes: list | None = None) -> dict:
    """Mapeia linha SQLite -> Product do front Lumina."""
    ean = (p.get("ean") or "").strip()
    codigo4 = (p.get("codigo_interno") or "").strip()
    sku = ean if ean and ean != "SEM GTIN" else codigo4
    return {
        "id": p.get("id"),
        "name": p.get("nome", ""),
        "sku": sku or codigo4,
        "codigo4": codigo4,
        "ean": ean or "SEM GTIN",
        "category": p.get("categoria") or "Alimentos",
        "price": float(p.get("preco_venda") or 0),
        "stock": float(p.get("quantidade_estoque") or 0),
        "color": p.get("cor") or "green",
        "unidade": p.get("unidade_medida") or "UN",
        "perfil_id": p.get("id_perfil_fiscal"),
        "perfil_nome": p.get("nome_perfil") or "",
        "validade": p.get("validade") or "",
        "lotes": lotes or [],
    }
