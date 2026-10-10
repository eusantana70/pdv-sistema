"""Criação do schema a partir de schema.sql (stdlib apenas)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .connection import connect

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def init_db(db_path: Path | None = None) -> Path:
    from .connection import get_db_path

    target = Path(db_path) if db_path else get_db_path()
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = connect(target)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
    return target


def table_counts(db_path: Path | None = None) -> dict:
    conn: sqlite3.Connection = connect(db_path)
    try:
        tables = [
            "produtos", "perfis_fiscais", "caixa_movimento", "caixa_operacoes",
            "vendas", "vendas_itens", "vendas_pagamentos", "configuracoes",
        ]
        out = {}
        for t in tables:
            out[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        return out
    finally:
        conn.close()
