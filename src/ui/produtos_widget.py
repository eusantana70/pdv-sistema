"""Gestão de Estoque/Produtos (M2): grid rápido com foco em velocidade.

Fluxo: Nome → Preço → Qtd → Perfil → [Adicionar] → limpa e foca Nome.
codigo_interno de 4 dígitos gerado no backend (repositories.criar_produto).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo

UNIDADES = ["UN", "KG", "G", "L", "ML", "PCT", "CX", "POTE"]


class ProdutosWidget(QWidget):
    HEADERS = ["ID", "Código", "Nome", "EAN", "Preço R$", "Estoque", "UN", "Perfil"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editing_id: int | None = None
        self._perfis: list = []
        self._build()
        self.recarregar_perfis()
        self.recarregar()

    # ----- layout -----
    def _build(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.ed_nome = QLineEdit(placeholderText="Nome do produto (Enter = adicionar)")
        self.ed_nome.returnPressed.connect(self.salvar)
        self.sp_preco = QDoubleSpinBox(minimum=0, maximum=999999, decimals=2,
                                       prefix="R$ ", singleStep=0.5)
        self.sp_qtd = QDoubleSpinBox(minimum=0, maximum=999999, decimals=3, singleStep=1)
        self.cb_perfil = QComboBox()
        self.ed_ean = QLineEdit(placeholderText="Opcional — default SEM GTIN")
        self.cb_un = QComboBox()
        self.cb_un.addItems(UNIDADES)
        form.addRow("Nome:", self.ed_nome)
        form.addRow("Preço venda:", self.sp_preco)
        form.addRow("Quantidade:", self.sp_qtd)
        form.addRow("Perfil fiscal:", self.cb_perfil)
        form.addRow("EAN/GTIN:", self.ed_ean)
        form.addRow("Unidade:", self.cb_un)
        lay.addLayout(form)

        linha = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self.salvar)
        self.btn_cancel = QPushButton("Cancelar edição")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._limpar_form)
        linha.addWidget(self.btn_add)
        linha.addWidget(self.btn_cancel)
        linha.addStretch(1)
        lay.addLayout(linha)

        busca_linha = QHBoxLayout()
        self.ed_busca = QLineEdit(placeholderText="Buscar por nome, código 4 dígitos ou EAN...")
        self.ed_busca.textChanged.connect(self.recarregar)
        self.btn_edit = QPushButton("Editar")
        self.btn_edit.clicked.connect(self._carregar_para_edicao)
        self.btn_del = QPushButton("Excluir")
        self.btn_del.clicked.connect(self.excluir)
        self.btn_desc = QPushButton("Desconto %")
        self.btn_desc.clicked.connect(self.desconto)
        busca_linha.addWidget(self.ed_busca, 1)
        busca_linha.addWidget(self.btn_edit)
        busca_linha.addWidget(self.btn_desc)
        busca_linha.addWidget(self.btn_del)
        lay.addLayout(busca_linha)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._carregar_para_edicao())
        lay.addWidget(self.table)

        self.lbl = QLabel("")
        self.lbl.setStyleSheet("color: #888;")
        lay.addWidget(self.lbl)

    # ----- dados -----
    def recarregar_perfis(self):
        conn = connect()
        try:
            self._perfis = repo.listar_perfis(conn)
        finally:
            conn.close()
        atual = self.cb_perfil.currentData()
        self.cb_perfil.clear()
        self.cb_perfil.addItem("(sem perfil)", None)
        for p in self._perfis:
            self.cb_perfil.addItem(p["nome_perfil"], p["id"])
        if atual is not None:
            idx = self.cb_perfil.findData(atual)
            if idx >= 0:
                self.cb_perfil.setCurrentIndex(idx)

    def recarregar(self):
        conn = connect()
        try:
            prods = repo.listar_produtos(conn, self.ed_busca.text())
        finally:
            conn.close()
        self.table.setRowCount(len(prods))
        for r, p in enumerate(prods):
            vals = [p["id"], p["codigo_interno"], p["nome"], p["ean"],
                    f'{float(p["preco_venda"]):.2f}',
                    ('%g' % float(p["quantidade_estoque"])),
                    p["unidade_medida"], p.get("nome_perfil") or ""]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c in (4, 5):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        self.lbl.setText(f"{len(prods)} produto(s). Enter no Nome = adicionar.")

    def salvar(self):
        conn = connect()
        try:
            if self.editing_id is None:
                p = repo.criar_produto(
                    conn, self.ed_nome.text(), self.sp_preco.value(),
                    self.sp_qtd.value(), self.cb_perfil.currentData(),
                    self.ed_ean.text() or "SEM GTIN", self.cb_un.currentText())
                self.lbl.setText(f'Adicionado: {p["nome"]} (código {p["codigo_interno"]}).')
            else:
                repo.atualizar_produto(
                    conn, self.editing_id, self.ed_nome.text(), self.sp_preco.value(),
                    self.sp_qtd.value(), self.cb_perfil.currentData(),
                    self.ed_ean.text() or "SEM GTIN", self.cb_un.currentText())
                self.lbl.setText("Produto atualizado.")
        except ValueError as e:
            QMessageBox.warning(self, "Produtos", str(e))
            conn.close()
            return
        except Exception as e:
            QMessageBox.critical(self, "Produtos", f"Erro ao salvar: {e}")
            conn.close()
            return
        conn.close()
        self._limpar_form()
        self.recarregar()

    def excluir(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Produtos", "Selecione uma linha.")
            return
        pid = int(self.table.item(row, 0).text())
        nome = self.table.item(row, 2).text()
        if QMessageBox.question(self, "Excluir", f"Excluir '{nome}'?") != QMessageBox.Yes:
            return
        conn = connect()
        try:
            repo.excluir_produto(conn, pid)
        except ValueError as e:
            QMessageBox.warning(self, "Produtos", str(e))
        finally:
            conn.close()
        self.recarregar()

    def desconto(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Desconto", "Selecione uma linha.")
            return
        pid = int(self.table.item(row, 0).text())
        nome = self.table.item(row, 2).text()
        pct, ok = QInputDialog.getDouble(self, "Desconto", f"Desconto % para '{nome}':",
                                         10, 0.01, 99.99, 2)
        if not ok:
            return
        conn = connect()
        try:
            novo = repo.aplicar_desconto(conn, pid, pct)
            QMessageBox.information(self, "Desconto", f"Novo preço: R$ {novo:.2f}")
        except ValueError as e:
            QMessageBox.warning(self, "Desconto", str(e))
        finally:
            conn.close()
        self.recarregar()

    def _carregar_para_edicao(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.editing_id = int(self.table.item(row, 0).text())
        conn = connect()
        try:
            p = repo.obter_produto(conn, self.editing_id)
        finally:
            conn.close()
        if not p:
            return
        self.ed_nome.setText(p["nome"])
        self.sp_preco.setValue(float(p["preco_venda"]))
        self.sp_qtd.setValue(float(p["quantidade_estoque"]))
        self.ed_ean.setText("" if p["ean"] == "SEM GTIN" else p["ean"])
        idx_un = self.cb_un.findText(p["unidade_medida"])
        self.cb_un.setCurrentIndex(idx_un if idx_un >= 0 else 0)
        idx_pf = self.cb_perfil.findData(p["id_perfil_fiscal"])
        self.cb_perfil.setCurrentIndex(idx_pf if idx_pf >= 0 else 0)
        self.btn_add.setText("Salvar")
        self.btn_cancel.setVisible(True)
        self.ed_nome.setFocus()
        self.ed_nome.selectAll()

    def _limpar_form(self):
        self.editing_id = None
        self.ed_nome.clear()
        self.sp_preco.setValue(0)
        self.sp_qtd.setValue(0)
        self.ed_ean.clear()
        self.cb_un.setCurrentIndex(0)
        self.btn_add.setText("Adicionar")
        self.btn_cancel.setVisible(False)
        self.recarregar_perfis()
        self.ed_nome.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar_perfis()
        self.recarregar()
