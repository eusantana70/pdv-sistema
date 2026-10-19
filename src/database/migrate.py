"""Migrações leves do SQLite — adiciona colunas novas sem perder dados.

Chamado em todo init da API (idempotente).
Cobre:
- produtos.categoria / produtos.cor / produtos.validade (front Lumina)
- produto_lotes (validades parciais por produto)
- vendas.desconto_percentual (desconto F3 do front)
- configuracoes.* (empresa + impressora + fiscal multi-provedor + desconto auto)
"""

from __future__ import annotations

import sqlite3


CONFIG_COLS: list[tuple[str, str]] = [    ("fiscal_provider", "TEXT DEFAULT 'mock'"),
    ("ambiente", "TEXT DEFAULT 'homologacao'"),
    ("modelo_doc", "TEXT DEFAULT 'NFC-e'"),
    ("serie", "TEXT DEFAULT '1'"),
    ("proximo_numero", "INTEGER DEFAULT 1"),
    ("razao_social", "TEXT DEFAULT ''"),
    ("nome_fantasia", "TEXT DEFAULT ''"),
    ("cnpj", "TEXT DEFAULT ''"),
    ("ie", "TEXT DEFAULT ''"),
    ("email", "TEXT DEFAULT ''"),
    ("telefone", "TEXT DEFAULT ''"),
    ("endereco", "TEXT DEFAULT ''"),
    ("cidade_uf", "TEXT DEFAULT ''"),
    ("cep", "TEXT DEFAULT ''"),
    ("impressora_largura", "TEXT DEFAULT '80mm'"),
    ("impressora_vias", "INTEGER DEFAULT 1"),
    ("auto_print", "INTEGER DEFAULT 1"),
    ("exibir_logo", "INTEGER DEFAULT 1"),
    ("corte_auto", "INTEGER DEFAULT 1"),
    ("mock_url", "TEXT DEFAULT 'http://localhost:3000'"),
    ("nuvem_token", "TEXT DEFAULT ''"),
    ("nuvem_url", "TEXT DEFAULT 'https://api.nuvemfiscal.com.br/nfce'"),
    ("focus_token", "TEXT DEFAULT ''"),
    ("focus_url", "TEXT DEFAULT 'https://api.focusnfe.com.br/v2/nfce'"),
    ("custom_token", "TEXT DEFAULT ''"),
    ("custom_url", "TEXT DEFAULT ''"),
    ("sefaz_cert_path", "TEXT DEFAULT ''"),
    ("sefaz_cert_senha", "TEXT DEFAULT ''"),
    ("desconto_tipo", "TEXT DEFAULT 'nenhum'"),
    ("desconto_valor", "REAL DEFAULT 0"),
    ("sessao_horas", "INTEGER DEFAULT 12"),
    # carimbo do primeiro acesso (criação do ADM no assistente inicial)
    ("setup_concluido_em", "TEXT DEFAULT ''"),
    # ---- Nota NÃO fiscal (comprovante impresso) ----
    ("recibo_titulo", "TEXT DEFAULT ''"),
    ("recibo_subtitulo", "TEXT DEFAULT 'Cupom de venda - sem valor fiscal'"),
    ("recibo_rodape", "TEXT DEFAULT 'Obrigado pela preferencia!'"),
    ("recibo_largura", "TEXT DEFAULT '48'"),
    ("recibo_mostrar_cnpj", "INTEGER DEFAULT 1"),
    ("recibo_mostrar_itens", "INTEGER DEFAULT 1"),
    ("recibo_mostrar_pagamentos", "INTEGER DEFAULT 1"),
    ("recibo_mostrar_troco", "INTEGER DEFAULT 1"),
    ("recibo_mostrar_atendente", "INTEGER DEFAULT 0"),
    ("recibo_mostrar_qrcode", "INTEGER DEFAULT 1"),
    # chaves de impressão (liga/desliga cada cupom)
    ("imprimir_cupom_fiscal", "INTEGER DEFAULT 1"),
    ("imprimir_cupom_nao_fiscal", "INTEGER DEFAULT 1"),
    # QR Code fixo por link + tributos + aviso de trocas
    ("recibo_qrcode_link", "TEXT DEFAULT ''"),
    ("recibo_tributos_federal", "REAL DEFAULT 0"),
    ("recibo_tributos_estadual", "REAL DEFAULT 0"),
    ("recibo_aviso_trocas", "TEXT DEFAULT 'Trocas somente mediante notinha'"),
    ("recibo_mostrar_tributos", "INTEGER DEFAULT 1"),
    ("recibo_mostrar_aviso_trocas", "INTEGER DEFAULT 1"),
]

PRODUTO_COLS: list[tuple[str, str]] = [
    ("categoria", "TEXT DEFAULT 'Alimentos'"),
    ("cor", "TEXT DEFAULT 'green'"),
    ("validade", "TEXT DEFAULT ''"),
]

VENDAS_COLS: list[tuple[str, str]] = [
    ("desconto_percentual", "REAL DEFAULT 0"),
]


def _cols(conn: sqlite3.Connection, tabela: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}


def _tabelas_acesso(conn: sqlite3.Connection) -> None:
    """Usuários (operadores/admin) e sessões de login."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'operador'
                CHECK (perfil IN ('admin','operador')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessoes (
            token TEXT PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            criado_em TEXT NOT NULL,
            expira_em TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessoes_user ON sessoes(id_usuario)")


def sistema_configurado(conn: sqlite3.Connection) -> bool:
    """True quando o primeiro acesso já criou o administrador.

    A regra é "existe ao menos um usuário ativo": nasce falso numa instalação
    nova (aí o assistente inicial aparece) e não tem como dessincronizar de
    uma flag, porque apaga junto com a tabela de usuários.
    """
    try:
        linha = conn.execute(
            "SELECT COUNT(*) AS c FROM usuarios WHERE ativo = 1"
        ).fetchone()
        return int(linha["c"] or 0) > 0
    except sqlite3.Error:
        return False


def marcar_setup_concluido(conn: sqlite3.Connection) -> None:
    """Grava o carimbo de 'primeiro acesso concluído'."""
    from datetime import datetime
    conn.execute(
        "UPDATE configuracoes SET setup_concluido_em = ? WHERE id = 1",
        (datetime.now().isoformat(timespec="seconds"),),
    )
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    # garante linha única de config
    conn.execute("INSERT OR IGNORE INTO configuracoes (id) VALUES (1)")
    existentes = _cols(conn, "configuracoes")
    for nome, ddl in CONFIG_COLS:
        if nome not in existentes:
            conn.execute(f"ALTER TABLE configuracoes ADD COLUMN {nome} {ddl}")
    pcols = _cols(conn, "produtos")
    for nome, ddl in PRODUTO_COLS:
        if nome not in pcols:
            conn.execute(f"ALTER TABLE produtos ADD COLUMN {nome} {ddl}")
    vcols = _cols(conn, "vendas")
    for nome, ddl in VENDAS_COLS:
        if nome not in vcols:
            conn.execute(f"ALTER TABLE vendas ADD COLUMN {nome} {ddl}")
    # lotes de validade por produto (permite ex.: 20 de 100 un. vencendo)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS produto_lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_produto INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
            validade TEXT NOT NULL,
            quantidade REAL NOT NULL CHECK (quantidade > 0)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lotes_prod ON produto_lotes(id_produto)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lotes_val ON produto_lotes(validade)")
    # migra validade única legada -> 1 lote com o estoque atual (uma vez só)
    try:
        legados = conn.execute(
            """SELECT p.id, p.validade, p.quantidade_estoque FROM produtos p
               WHERE p.validade IS NOT NULL AND p.validade <> ''
               AND NOT EXISTS (SELECT 1 FROM produto_lotes l WHERE l.id_produto = p.id)"""
        ).fetchall()
        for leg in legados:
            try:
                conn.execute(
                    "INSERT INTO produto_lotes (id_produto, validade, quantidade) VALUES (?, ?, ?)",
                    (leg["id"], leg["validade"], max(float(leg["quantidade_estoque"] or 0), 1)),
                )
            except Exception:
                pass
    except Exception:
        pass
    _tabelas_acesso(conn)
    conn.commit()
