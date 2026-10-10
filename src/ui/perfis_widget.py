"""Tela de Perfis Fiscais (M1): cadastra NCM/CFOP/CSOSN uma única vez."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo


class PerfisWidget(QWidget):
    HEADERS = ["ID", "Perfil", "NCM", "CFOP", "CSOSN", "Origem"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editing_id: int | None = None
        self._build()
        self.recarregar()

    def _build(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.ed_nome = QLineEdit(placeholderText="Ex: Sorvetes Tributação Normal")
        self.ed_ncm = QLineEdit(placeholderText="Ex: 2105.00.10")
        self.ed_cfop = QLineEdit(text="5102")
        self.ed_csosn = QLineEdit(placeholderText="Ex: 102")
        self.ed_origem = QComboBox()
        self.ed_origem.addItems(["0 - Nacional", "1 - Estrangeira (importação direta)",
                                 "2 - Estrangeira (mercado interno)"])
        form.addRow("Nome do perfil:", self.ed_nome)
        form.addRow("NCM:", self.ed_ncm)
        form.addRow("CFOP:", self.ed_cfop)
        form.addRow("CSOSN:", self.ed_csosn)
        form.addRow("Origem:", self.ed_origem)
        lay.addLayout(form)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self.salvar)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._limpar_form)
        self.btn_del = QPushButton("Excluir selecionado")
        self.btn_del.clicked.connect(self.excluir)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_cancel)
        btns.addStretch(1)
        btns.addWidget(self.btn_del)
        lay.addLayout(btns)

        lay.addWidget(QLabel("Perfis cadastrados (usados no cadastro de produtos):"))
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._carregar_para_edicao)
        lay.addWidget(self.table)

        hint = QLabel("Duplo-clique numa linha para editar. Excluir falha se houver produto usando o perfil.")
        hint.setStyleSheet("color: #888;")
        lay.addWidget(hint)

    # ----- dados -----
    def recarregar(self):
        conn = connect()
        try:
            perfis = repo.listar_perfis(conn)
        finally:
            conn.close()
        self.table.setRowCount(len(perfis))
        for r, p in enumerate(perfis):
            vals = [p["id"], p["nome_perfil"], p["ncm"], p["cfop"], p["csosn"], p["origem"]]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))

    def salvar(self):
        origem = self.ed_origem.currentText().split(" - ")[0]
        conn = connect()
        try:
            if self.editing_id is None:
                repo.criar_perfil(conn, self.ed_nome.text(), self.ed_ncm.text(),
                                  self.ed_cfop.text() or "5102",
                                  self.ed_csosn.text(), origem)
            else:
                repo.atualizar_perfil(conn, self.editing_id, self.ed_nome.text(),
                                      self.ed_ncm.text(), self.ed_cfop.text(),
                                      self.ed_csosn.text(), origem)
        except ValueError as e:
            QMessageBox.warning(self, "Perfil fiscal", str(e))
            conn.close()
            return
        except Exception as e:  # UNIQUE nome_perfil
            QMessageBox.critical(self, "Perfil fiscal", f"Erro ao salvar: {e}")
            conn.close()
            return
        conn.close()
        self._limpar_form()
        self.recarregar()

    def excluir(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Perfil fiscal", "Selecione uma linha.")
            return
        pid = int(self.table.item(row, 0).text())
        nome = self.table.item(row, 1).text()
        if QMessageBox.question(self, "Excluir", f"Excluir perfil '{nome}'?") != QMessageBox.Yes:
            return
        conn = connect()
        try:
            repo.excluir_perfil(conn, pid)
        except ValueError as e:
            QMessageBox.warning(self, "Perfil fiscal", str(e))
        finally:
            conn.close()
        self.recarregar()

    def _carregar_para_edicao(self, row, _col):
        self.editing_id = int(self.table.item(row, 0).text())
        self.ed_nome.setText(self.table.item(row, 1).text())
        self.ed_ncm.setText(self.table.item(row, 2).text())
        self.ed_cfop.setText(self.table.item(row, 3).text())
        self.ed_csosn.setText(self.table.item(row, 4).text())
        origem = self.table.item(row, 5).text()
        idx = next((i for i in range(self.ed_origem.count())
                    if self.ed_origem.itemText(i).startswith(origem)), 0)
        self.ed_origem.setCurrentIndex(idx)
        self.btn_add.setText("Salvar")
        self.btn_cancel.setVisible(True)
        self.ed_nome.setFocus()

    def _limpar_form(self):
        self.editing_id = None
        self.ed_nome.clear()
        self.ed_ncm.clear()
        self.ed_cfop.setText("5102")
        self.ed_csosn.clear()
        self.ed_origem.setCurrentIndex(0)
        self.btn_add.setText("Adicionar")
        self.btn_cancel.setVisible(False)
        self.ed_nome.setFocus()
