"""Inicializa data/pdv.db com o schema. Usa só stdlib (sem pip install)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from database.schema import init_db, table_counts

if __name__ == "__main__":
    db = init_db()
    print(f"Banco criado/verificado em: {db}")
    print(table_counts())
