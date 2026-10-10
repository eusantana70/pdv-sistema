"""Modal de pagamento com split + troco (M5).

Regra: total R$ 50, paga R$ 15 no PIX → saldo R$ 35 até zerar.
Excedente (troco) só permitido em dinheiro; cartão/PIX exigem valor exato.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QListWidget, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout,
)

from services.pagamentos import SplitPagamento


class PagamentoDialog(QDialog):
    def __init__(self, total: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Pagamento — Total R$ {total:.2f}")
        self.setModal(True)
        self.resize(440, 520)
        self.split = SplitPagamento(total=round(total, 2))
        self._build()
        self._refresh()

    def _build(self):
        lay = QVBoxLayout(self)

        self.lbl_total = QLabel(f"TOTAL: R$ {self.split.total:.2f}")
        self.lbl_total.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.lbl_total.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_total)

        self.lbl_saldo = QLabel("")
        self.lbl_saldo.setAlignment(Qt.AlignCenter)
        self.lbl_saldo.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px;")
        lay.addWidget(self.lbl_saldo)

        self.lbl_troco = QLabel("")
        self.lbl_troco.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_troco)

        lay.addWidget(QLabel("Adicionar pagamento:"))
        linha = QHBoxLayout()
        self.sp_valor = QDoubleSpinBox(minimum=0.01, maximum=1e9, decimals=2,
                                       prefix="R$ ", value=self.split.total)
        self.sp_valor.setMinimumWidth(130)
        self.cb_metodo = QComboBox()
        self.cb_metodo.addItems(["dinheiro", "pix", "debito", "credito"])
        self.sp_parc = QSpinBox(minimum=1, maximum=12, prefix="Parc ")
        self.sp_parc.setVisible(False)
        self.cb_metodo.currentTextChanged.connect(
            lambda t: self.sp_parc.setVisible(t == "credito"))
        linha.addWidget(self.sp_valor, 1)
        linha.addWidget(self.cb_metodo)
        linha.addWidget(self.sp_parc)
        lay.addLayout(linha)

        btns_add = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self._adicionar)
        self.btn_rm = QPushButton("Remover selecionado")
        self.btn_rm.clicked.connect(self._remover)
        btns_add.addWidget(self.btn_add)
        btns_add.addWidget(self.btn_rm)
        lay.addLayout(btns_add)

        lay.addWidget(QLabel("Pagamentos lançados:"))
        self.lst = QListWidget()
        lay.addWidget(self.lst, 1)

        self.box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.box.button(QDialogButtonBox.Ok).setText("Confirmar venda")
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        lay.addWidget(self.box)

    def _adicionar(self):
        metodo = self.cb_metodo.currentText()
        valor = round(self.sp_valor.value(), 2)
        parc = self.sp_parc.value() if metodo == "credito" else 1
        saldo = self.split.saldo_restante()
        if valor <= 0:
            QMessageBox.warning(self, "Pagamento", "Valor deve ser > 0.")
            return
        if metodo != "dinheiro" and valor - saldo > 0.001:
            QMessageBox.warning(
                self, "Pagamento",
                f"{metodo} não gera troco. Máximo restante: R$ {saldo:.2f}.")
            return
        try:
            novo_saldo = self.split.adicionar(metodo, valor, parc)
        except ValueError as e:
            QMessageBox.warning(self, "Pagamento", str(e))
            return
        if novo_saldo > 0:
            self.sp_valor.setValue(novo_saldo)
        self._refresh()

    def _remover(self):
        row = self.lst.currentRow()
        if row < 0 or row >= len(self.split.partes):
            return
        self.split.partes.pop(row)
        self._refresh()
        if self.split.saldo_restante() > 0:
            self.sp_valor.setValue(self.split.saldo_restante())

    def _refresh(self):
        saldo = self.split.saldo_restante()
        troco = self.split.troco()
        self.lst.clear()
        for p in self.split.partes:
            extra = f" {p.parcelas}x" if p.metodo == "credito" else ""
            self.lst.addItem(f"{p.metodo}{extra} — R$ {p.valor:.2f}")
        if saldo > 0:
            self.lbl_saldo.setText(f"FALTA: R$ {saldo:.2f}")
            self.lbl_saldo.setStyleSheet(
                "font-size: 18px; font-weight: bold; padding: 8px; "
                "background: #f38ba8; color: #11111b; border-radius: 8px;")
        else:
            self.lbl_saldo.setText("PAGAMENTO COMPLETO")
            self.lbl_saldo.setStyleSheet(
                "font-size: 18px; font-weight: bold; padding: 8px; "
                "background: #a6e3a1; color: #11111b; border-radius: 8px;")
        self.lbl_troco.setText(f"Troco: R$ {troco:.2f}" if troco > 0 else "")
        self.box.button(QDialogButtonBox.Ok).setEnabled(self.split.concluido())

    def pagamentos(self) -> list:
        return [{"metodo": p.metodo, "valor": p.valor, "parcelas": p.parcelas}
                for p in self.split.partes]

    def troco(self) -> float:
        return self.split.troco()
