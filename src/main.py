"""Entry point do PDV. Roda sem dependências externas até a UI ser instalada."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection import get_db_path  # noqa: E402
from database.schema import init_db, table_counts  # noqa: E402


def main() -> int:
    db_path = init_db()
    counts = table_counts()
    print(f"PDV Sistema — banco pronto em: {db_path}")
    print(f"Tabelas: {counts}")
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(
            "\nUI PySide6 ainda não instalada (de propósito: aguardando sua decisão de onde instalar).\n"
            "Quando liberar, rode os comandos do README (opção A ou B) e depois: python src\\main.py"
        )
        return 0
    # TODO: iniciar QApplication + janela principal (Módulos 1-7)
    print("PySide6 detectado. UI principal ainda será implementada no próximo passo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
