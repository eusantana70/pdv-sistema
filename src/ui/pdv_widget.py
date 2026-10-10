"""Frente de Caixa / PDV (M4): busca, carrinho, total. Exige caixa aberto.

Finalização aqui é simples (1 pagamento do total); o split detalhado chega no M5.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo
from services.carrinho import Carrinho


class PdvWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cart = Carrinho()
        self._sugestoes: list = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        self.lbl_caixa = QLabel("")
        self.lbl_caixa.setAlignment(Qt.AlignCenter)
        self.lbl_caixa.setStyleSheet("font-weight: bold; padding: 8px;")
        lay.addWidget(self.lbl_caixa)

        busca = QHBoxLayout()
        self.ed_busca = QLineEdit(placeholderText="Buscar por nome ou código 4 dígitos...")
        self.ed_busca.textChanged.connect(self._sugerir)
        self.ed_busca.returnPressed.connect(self._enter_busca)
        self.sp_qtd = QDoubleSpinBox(minimum=0.001, maximum=9999, decimals=3, value=1)
        self.sp_qtd.setPrefix("Qtd ")
        self.sp_qtd.setMinimumWidth(110)
        self.btn_add = QPushButton("Adicionar (Enter)")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self._adicionar_selecionado)
        busca.addWidget(self.ed_busca, 1)
        busca.addWidget(self.sp_qtd)
        busca.addWidget(self.btn_add)
        lay.addLayout(busca)

        self.lst = QListWidget()
        self.lst.setMaximumHeight(130)
        self.lst.itemActivated.connect(lambda _i: self._adicionar_selecionado())
        self.lst.itemClicked.connect(lambda _i: self._adicionar_selecionado())
        lay.addWidget(self.lst)

        lay.addWidget(QLabel("Itens da venda (carrinho):"))
        self.tb = QTableWidget(0, 5)
        self.tb.setHorizontalHeaderLabels(["Código", "Nome", "Qtd", "Unit R$", "Subtotal R$"])
        self.tb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb.verticalHeader().setVisible(False)
        self.tb.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tb, 1)

        rodape = QHBoxLayout()
        self.lbl_total = QLabel("TOTAL  R$ 0,00")
        self.lbl_total.setStyleSheet(
            "font-size: 28px; font-weight: bold; background: #11111b; color: #a6e3a1; "
            "padding: 12px; border-radius: 10px;")
        rodape.addWidget(self.lbl_total, 1)

        col = QVBoxLayout()
        self.cb_pagto = QComboBox()
        self.cb_pagto.addItems(["dinheiro", "pix", "debito", "credito"])
        self.sp_parc = QSpinBox(minimum=1, maximum=12, value=1, prefix="Parc ")
        self.sp_parc.setVisible(False)
        self.cb_pagto.currentTextChanged.connect(
            lambda t: self.sp_parc.setVisible(t == "credito"))
        self.btn_rm = QPushButton("Remover item")
        self.btn_rm.clicked.connect(self._remover)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self._limpar)
        self.btn_fim = QPushButton("FINALIZAR VENDA")
        self.btn_fim.setMinimumHeight(56)
        self.btn_fim.setStyleSheet("font-size: 18px;")
        self.btn_fim.clicked.connect(self.finalizar)
        col.addWidget(QLabel("Pagamento:"))
        col.addWidget(self.cb_pagto)
        col.addWidget(self.sp_parc)
        col.addWidget(self.btn_rm)
        col.addWidget(self.btn_limpar)
        col.addWidget(self.btn_fim)
        rodape.addLayout(col)
        lay.addLayout(rodape)

    # ----- busca / carrinho -----
    def _sugerir(self, texto):
        conn = connect()
        try:
            self._sugestoes = repo.buscar_para_pdv(conn, texto, 20)
        finally:
            conn.close()
        self.lst.clear()
        for p in self._sugestoes:
            self.lst.addItem(
                f'{p["codigo_interno"]}  •  {p["nome"]}  •  R$ {float(p["preco_venda"]):.2f}  '
                f'(est {float(p["quantidade_estoque"]):g} {p["unidade_medida"]})')

    def _enter_busca(self):
        if self._sugestoes:
            self.lst.setCurrentRow(0)
            self._adicionar_selecionado()

    def _adicionar_selecionado(self):
        row = self.lst.currentRow()
        if row < 0 and self._sugestoes:
            row = 0
        if row < 0 or row >= len(self._sugestoes):
            return
        prod = self._sugestoes[row]
        try:
            self.cart.adicionar(prod, self.sp_qtd.value())
        except ValueError as e:
            QMessageBox.warning(self, "PDV", str(e))
            return
        self._pintar_carrinho()
        self.ed_busca.clear()
        self.ed_busca.setFocus()

    def _pintar_carrinho(self):
        self.tb.setRowCount(len(self.cart.itens))
        for r, i in enumerate(self.cart.itens):
            for c, v in enumerate([i.codigo_interno, i.nome, ('%g' % i.quantidade),
                                   f"{i.valor_unitario:.2f}", f"{i.subtotal:.2f}"]):
                item = QTableWidgetItem(str(v))
                if c >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tb.setItem(r, c, item)
        self.lbl_total.setText(f"TOTAL  R$ {self.cart.total():.2f}".replace(".", ","))

    def _remover(self):
        row = self.tb.currentRow()
        if row < 0:
            return
        self.cart.remover(row)
        self._pintar_carrinho()

    def _limpar(self):
        self.cart.limpar()
        self._pintar_carrinho()

    def finalizar(self):
        if self.cart.vazio():
            QMessageBox.information(self, "PDV", "Carrinho vazio.")
            return
        conn = connect()
        try:
            mov = repo.obter_caixa_aberto(conn)
            if not mov:
                QMessageBox.warning(self, "PDV", "Caixa fechado. Abra o caixa antes de vender.")
                return
            metodo = self.cb_pagto.currentText()
            pagto = {"metodo": metodo, "valor": self.cart.total(),
                     "parcelas": self.sp_parc.value() if metodo == "credito" else 1}
            venda = repo.criar_venda(conn, mov["id"], self.cart.para_venda(), [pagto])
        except ValueError as e:
            QMessageBox.warning(self, "PDV", str(e))
            conn.close()
            return
        except Exception as e:
            QMessageBox.critical(self, "PDV", f"Erro ao finalizar: {e}")
            conn.close()
            return
        conn.close()
        QMessageBox.information(
            self, "PDV",
            f'Venda #{venda["id"]} concluída: R$ {float(venda["total"]):.2f} ({metodo}).\n'
            "Estoque deduzido. (Split de pagamentos chega no M5.)")
        self._limpar()
        self._sugerir("")

    def showEvent(self, event):
        super().showEvent(event)
        conn = connect()
        try:
            mov = repo.obter_caixa_aberto(conn)
        finally:
            conn.close()
        if mov:
            self.lbl_caixa.setText(f'Caixa #{mov["id"]} ABERTO — pode vender')
            self.lbl_caixa.setStyleSheet(
                "font-weight: bold; padding: 8px; background: #a6e3a1; color: #11111b; border-radius: 8px;")
            self._set_enabled(True)
        else:
            self.lbl_caixa.setText("CAIXA FECHADO — vá na aba Caixa e clique em ABRIR CAIXA")
            self.lbl_caixa.setStyleSheet(
                "font-weight: bold; padding: 8px; background: #f38ba8; color: #11111b; border-radius: 8px;")
            self._set_enabled(False)
        self._sugerir(self.ed_busca.text())

    def _set_enabled(self, on: bool):
        for w in (self.ed_busca, self.sp_qtd, self.btn_add, self.lst, self.tb,
                  self.cb_pagto, self.sp_parc, self.btn_rm, self.btn_limpar, self.btn_fim):
            w.setEnabled(on)
