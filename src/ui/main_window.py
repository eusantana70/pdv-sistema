"""Janela principal do PDV — tema comercial, tela cheia, 6 módulos."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from .pdv_widget import PdvWidget
from .caixa_widget import CaixaWidget
from .historico_widget import HistoricoWidget
from .produtos_widget import ProdutosWidget
from .perfis_widget import PerfisWidget
from .config_widget import ConfigWidget

# Tema comercial escuro-premium: fundo slate, acento âmbar (sorveteria),
# tipografia grande para operação em tela cheia / touchscreen.
QSS = """
QMainWindow { background: #161a23; }
QWidget { font-size: 15px; }
QToolTip { background: #232936; color: #f2f4f8; border: 1px solid #3a4356; padding: 6px; }

/* Abas grandes, legíveis a distância */
QTabWidget::pane { border: 0; background: #161a23; margin-top: 6px; }
QTabBar::tab {
    background: #232936; color: #c6cfdd;
    padding: 14px 26px; margin-right: 6px;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
    font-size: 16px; font-weight: 600;
}
QTabBar::tab:hover { background: #2e3648; color: #ffffff; }
QTabBar::tab:selected { background: #f5a623; color: #1a1305; }

/* Campos: altos, com foco visível */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit {
    background: #232936; color: #f2f4f8;
    border: 1px solid #3a4356; border-radius: 8px; padding: 10px;
    selection-background-color: #f5a623; selection-color: #1a1305;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 2px solid #f5a623;
}
QComboBox QAbstractItemView, QAbstractItemView {
    background: #232936; color: #f2f4f8; selection-background-color: #f5a623;
}

/* Botões comerciais: altos para touchscreen */
QPushButton {
    background: #2e7cf6; color: #ffffff; border: 0; border-radius: 10px;
    padding: 12px 20px; font-weight: 700; font-size: 15px; min-height: 20px;
}
QPushButton:hover { background: #4d94ff; }
QPushButton:pressed { background: #1f5fd0; }
QPushButton:disabled { background: #2a3140; color: #6b7688; }

/* Tabelas: linhas alternadas, cabeçalho forte */
QTableWidget, QListWidget {
    background: #1c2230; color: #eef1f6; alternate-background-color: #202839;
    gridline-color: #2c3547; border: 1px solid #2c3547; border-radius: 10px;
    selection-background-color: #f5a623; selection-color: #1a1305;
    font-size: 15px;
}
QHeaderView::section {
    background: #2e3648; color: #ffffff; padding: 10px;
    border: 0; font-weight: 700; font-size: 14px;
}
QLabel { color: #dfe5ef; }
QStatusBar { background: #10141c; color: #9aa5b8; font-size: 13px; }
QScrollBar:vertical { background: transparent; width: 12px; }
QScrollBar::handle:vertical { background: #3a4356; border-radius: 6px; min-height: 30px; }
QDialog { background: #1c2230; }
"""

APP_VERSION = "1.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDV Sorvetes — Franquia MG")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)
        self.setStyleSheet(QSS)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(PdvWidget(), "Frente de Caixa")
        tabs.addTab(CaixaWidget(), "Caixa")
        tabs.addTab(HistoricoWidget(), "Histórico / Relatórios")
        tabs.addTab(ProdutosWidget(), "Estoque / Produtos")
        tabs.addTab(PerfisWidget(), "Perfis Fiscais")
        tabs.addTab(ConfigWidget(), "Configurações")
        self.setCentralWidget(tabs)

        status = QStatusBar()
        try:
            from database.connection import get_db_path
            status.showMessage(f"PDV Sorvetes v{APP_VERSION}   •   Banco: {get_db_path()}")
        except Exception:
            status.showMessage(f"PDV Sorvetes v{APP_VERSION}")
        self.setStatusBar(status)
