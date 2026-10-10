"""Janela principal do PDV — M1-M4 (M5-M7 entram como novas abas/dialogs)."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from .pdv_widget import PdvWidget
from .caixa_widget import CaixaWidget
from .produtos_widget import ProdutosWidget
from .perfis_widget import PerfisWidget
from .config_widget import ConfigWidget

QSS = """
QMainWindow { background: #1e1e2e; }
QWidget { font-size: 14px; }
QTabWidget::pane { border: 0; background: #1e1e2e; }
QTabBar::tab { background: #313244; color: #cdd6f4; padding: 10px 18px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: #89b4fa; color: #11111b; font-weight: bold; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 8px; }
QPushButton { background: #89b4fa; color: #11111b; border: 0; border-radius: 8px; padding: 10px 16px; font-weight: bold; }
QPushButton:hover { background: #b4befe; }
QPushButton:disabled { background: #45475a; color: #7f849c; }
QTableWidget, QListWidget { background: #181825; color: #cdd6f4; gridline-color: #313244; border: 1px solid #313244; border-radius: 8px; }
QHeaderView::section { background: #313244; color: #cdd6f4; padding: 8px; border: 0; }
QLabel { color: #cdd6f4; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDV Sorvetes — Franquia MG")
        self.resize(1100, 700)
        self.setStyleSheet(QSS)

        tabs = QTabWidget()
        tabs.addTab(PdvWidget(), "Frente de Caixa")
        tabs.addTab(CaixaWidget(), "Caixa")
        tabs.addTab(ProdutosWidget(), "Estoque / Produtos")
        tabs.addTab(PerfisWidget(), "Perfis Fiscais")
        tabs.addTab(ConfigWidget(), "Configurações")
        self.setCentralWidget(tabs)
