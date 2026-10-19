"""Dependências compartilhadas da API (conexão SQLite por request)."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database.connection import connect, get_db_path


def get_conn() -> sqlite3.Connection:
    conn = connect(get_db_path())
    try:
        yield conn
    finally:
        conn.close()
