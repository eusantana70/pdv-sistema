"""Conexão SQLite (arquivo único no %LOCALAPPDATA% do usuário). Sem dependências externas."""

from __future__ import annotations

import sqlite3
from pathlib import Path

# O banco fica sempre fora da pasta do programa: %LOCALAPPDATA%\PDV Lumina\pdv.db
# (ver src/core/paths.py). Assim o instalador pode ir para Program Files e o
# dado do usuário sobrevive a atualizar/desinstalar o programa.
try:
    from core.paths import caminho_db
except ImportError:  # roda como src.database.connection
    from src.core.paths import caminho_db

DEFAULT_DB_PATH = caminho_db()


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: o FastAPI roda dependências e rotas em threads
    # diferentes do pool (a conexão nasce numa e é usada/fechada noutra) — sem isso
    # cai em "sqlite3.ProgrammingError: objects created in a thread can only be
    # used in that same thread". Cada requisição usa a sua conexão isoladamente.
    # timeout/busy_timeout evitam "database is locked" com o worker fiscal.
    conn = sqlite3.connect(str(path), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn