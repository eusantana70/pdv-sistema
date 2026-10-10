"""Conexão SQLite (arquivo único local). Sem dependências externas."""

from __future__ import annotations

import sqlite3
from pathlib import Path

# data/pdv.db na raiz do projeto (ou %LOCALAPPDATA%/pdv-sistema/pdv.db no .exe)
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "data" / "pdv.db"


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn
