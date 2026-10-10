"""Entry point do PDV. Garante DB e abre a UI PySide6 (M1/M2)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
for _p in (str(SRC), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database.connection import get_db_path  # noqa: E402
from database.schema import init_db, table_counts  # noqa: E402


def main() -> int:
    db_path = init_db()
    counts = table_counts()
    print(f"PDV Sistema — banco pronto em: {db_path}")
    print(f"Tabelas: {counts}")
    try:
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
    except ImportError:
        print("\nPySide6 não instalado. Ative o venv e rode: pip install -r requirements.txt")
        return 1
    app = QApplication(sys.argv)
    try:
        from PySide6.QtGui import QFont
        app.setFont(QFont("Segoe UI", 10))
    except Exception:
        pass
    win = MainWindow()
    win.showMaximized()  # visual comercial em tela cheia
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
