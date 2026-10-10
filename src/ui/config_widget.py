"""Tela de Configurações (M1): API fiscal + impressora térmica."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo
from services.impressoras import listar_impressoras, impressora_padrao


class ConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self.carregar()

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.ed_token = QLineEdit(placeholderText="Token da Nuvem Fiscal / Focus NFe")
        self.ed_token.setEchoMode(QLineEdit.Password)
        self.ed_url = QLineEdit(placeholderText="Ex: https://api.nuvemfiscal.com.br/nfce")
        self.cb_imp = QComboBox()
        self.cb_imp.setEditable(True)
        form.addRow("API NFC-e token:", self.ed_token)
        form.addRow("API NFC-e URL:", self.ed_url)
        form.addRow("Impressora térmica:", self.cb_imp)
        lay.addLayout(form)

        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("Detectar impressoras")
        self.btn_refresh.clicked.connect(self.detectar)
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self.salvar)
        btns.addWidget(self.btn_refresh)
        btns.addStretch(1)
        btns.addWidget(self.btn_save)
        lay.addLayout(btns)

        self.lbl = QLabel("")
        self.lbl.setStyleSheet("color: #888;")
        lay.addWidget(self.lbl)
        lay.addStretch(1)

    def detectar(self):
        atual = self.cb_imp.currentText()
        imps = listar_impressoras()
        self.cb_imp.clear()
        if imps:
            self.cb_imp.addItems(imps)
            if atual in imps:
                self.cb_imp.setCurrentText(atual)
            else:
                padrao = impressora_padrao()
                if padrao in imps:
                    self.cb_imp.setCurrentText(padrao)
            self.lbl.setText(f"{len(imps)} impressora(s) encontrada(s).")
        else:
            self.lbl.setText("Nenhuma impressora encontrada (win32print indisponível ou sem impressoras). "
                             "Digite o nome manualmente.")

    def carregar(self):
        conn = connect()
        try:
            cfg = repo.obter_config(conn)
        finally:
            conn.close()
        self.ed_token.setText(cfg.get("api_nfce_token", ""))
        self.ed_url.setText(cfg.get("api_nfce_url", ""))
        nome = cfg.get("impressora_nome", "")
        self.detectar()
        if nome and self.cb_imp.findText(nome) < 0:
            self.cb_imp.addItem(nome)
        if nome:
            self.cb_imp.setCurrentText(nome)

    def salvar(self):
        conn = connect()
        try:
            repo.salvar_config(conn, self.ed_token.text(), self.ed_url.text(),
                               self.cb_imp.currentText())
        finally:
            conn.close()
        QMessageBox.information(self, "Configurações", "Salvo com sucesso.")
