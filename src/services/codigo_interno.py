"""Geração de codigo_interno de 4 dígitos únicos (Módulo 2)."""

from __future__ import annotations

import random
import sqlite3


def gerar_codigo_interno(conn: sqlite3.Connection) -> str:
    """Gera string de 4 dígitos (1000-9999) que ainda não existe em produtos."""
    for _ in range(9000):
        codigo = f"{random.randint(1000, 9999):04d}"
        cur = conn.execute(
            "SELECT 1 FROM produtos WHERE codigo_interno = ?", (codigo,)
        )
        if cur.fetchone() is None:
            return codigo
    raise RuntimeError("Sem códigos internos de 4 dígitos disponíveis.")
