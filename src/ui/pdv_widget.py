"""Frente de Caixa / PDV (M4+M5): busca, carrinho, total e split de pagamento.

Exige caixa aberto. Finalizar abre o modal de pagamento (M5).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo
from services.carrinho import Carrinho
from ui.pagamento_dialog import PagamentoDialog


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
        self.ed_busca = QLineEdit(placeholderText="Buscar por nome ou código 4 dígitos...  (F2 foca aqui)")
        self.ed_busca.textChanged.connect(self._sugerir)
        self.ed_busca.returnPressed.connect(self._enter_busca)
        self.sp_qtd = QDoubleSpinBox(minimum=0.001, maximum=9999, decimals=3, value=1)
        self.sp_qtd.setPrefix("Qtd ")
        self.sp_qtd.setMinimumWidth(130)
        self.sp_qtd.setMinimumHeight(48)
        self.ed_busca.setMinimumHeight(48)
        self.btn_add = QPushButton("Adicionar (Enter)")
        self.btn_add.setDefault(True)
        self.btn_add.setMinimumHeight(48)
        self.btn_add.setMinimumWidth(200)
        self.btn_add.clicked.connect(self._adicionar_selecionado)
        busca.addWidget(self.ed_busca, 1)
        busca.addWidget(self.sp_qtd)
        busca.addWidget(self.btn_add)
        lay.addLayout(busca)

        self.lst = QListWidget()
        self.lst.setMaximumHeight(150)
        self.lst.setAlternatingRowColors(True)
        self.lst.itemActivated.connect(lambda _i: self._adicionar_selecionado())
        self.lst.itemClicked.connect(lambda _i: self._adicionar_selecionado())
        lay.addWidget(self.lst)

        lay.addWidget(QLabel("Itens da venda (carrinho):"))
        self.tb = QTableWidget(0, 5)
        self.tb.setHorizontalHeaderLabels(["Código", "Nome", "Qtd", "Unit R$", "Subtotal R$"])
        self.tb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb.setAlternatingRowColors(True)
        self.tb.verticalHeader().setVisible(False)
        self.tb.verticalHeader().setDefaultSectionSize(34)
        hdr = self.tb.horizontalHeader()
        hdr.setStretchLastSection(False)
        from PySide6.QtWidgets import QHeaderView
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        lay.addWidget(self.tb, 1)

        rodape = QHBoxLayout()
        rodape.setSpacing(12)
        self.lbl_total = QLabel("TOTAL  R$ 0,00")
        self.lbl_total.setAlignment(Qt.AlignCenter)
        self.lbl_total.setStyleSheet(
            "font-size: 40px; font-weight: 900; background: #0e2a1a; color: #7CFC9a; "
            "padding: 16px; border-radius: 14px; border: 2px solid #1f5c38;")
        rodape.addWidget(self.lbl_total, 1)

        col = QVBoxLayout()
        col.setSpacing(8)
        self.btn_rm = QPushButton("Remover item")
        self.btn_rm.setMinimumHeight(44)
        self.btn_rm.clicked.connect(self._remover)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.setMinimumHeight(44)
        self.btn_limpar.clicked.connect(self._limpar)
        self.btn_fim = QPushButton("FINALIZAR (F5)")
        self.btn_fim.setMinimumHeight(72)
        self.btn_fim.setMinimumWidth(240)
        self.btn_fim.setStyleSheet(
            "font-size: 20px; background: #f5a623; color: #1a1305; border-radius: 12px;")
        self.btn_fim.setShortcut("F5")
        self.btn_fim.clicked.connect(self.finalizar)
        col.addWidget(QLabel("Split e troco no modal:"))
        col.addWidget(self.btn_rm)
        col.addWidget(self.btn_limpar)
        col.addWidget(self.btn_fim)
        rodape.addLayout(col)
        lay.addLayout(rodape)

        try:
            from PySide6.QtGui import QShortcut, QKeySequence
            QShortcut(QKeySequence("F2"), self, activated=lambda: (
                self.ed_busca.setFocus(), self.ed_busca.selectAll()))
        except Exception:
            pass

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
        finally:
            conn.close()
        if not mov:
            QMessageBox.warning(self, "PDV", "Caixa fechado. Abra o caixa antes de vender.")
            return
        dlg = PagamentoDialog(self.cart.total(), self)
        if dlg.exec() != PagamentoDialog.Accepted:
            return
        pagamentos = dlg.pagamentos()
        troco = dlg.troco()
        conn = connect()
        try:
            venda = repo.criar_venda(conn, mov["id"], self.cart.para_venda(), pagamentos)
        except ValueError as e:
            QMessageBox.warning(self, "PDV", str(e))
            conn.close()
            return
        except Exception as e:
            QMessageBox.critical(self, "PDV", f"Erro ao finalizar: {e}")
            conn.close()
            return
        conn.close()
        msg_troco = f"\nTroco: R$ {troco:.2f}" if troco > 0 else ""
        QMessageBox.information(
            self, "PDV",
            f'Venda #{venda["id"]} concluída: R$ {float(venda["total"]):.2f} '
            f'({len(pagamentos)} pagamento(s)).{msg_troco}\nEstoque deduzido.')
        try:
            self._pos_venda(venda)
        except AttributeError:
            pass
        self._limpar()
        self._sugerir("")

    def _pos_venda(self, venda: dict):
        """M6: dispara emissão fiscal async; ao concluir pergunta impressão."""
        try:
            from database.connection import get_db_path
            from services.fiscal import FiscalThread
        except ImportError:
            return
        if FiscalThread is None:
            return
        self._fiscal = FiscalThread(get_db_path(), venda["id"], self)
        self._fiscal.ok.connect(self._fiscal_ok)
        self._fiscal.falha.connect(self._fiscal_falha)
        self._fiscal.start()

    def _fiscal_ok(self, venda_id: int):
        self._perguntar_impressao(
            venda_id, "NFC-e autorizada! Deseja imprimir o cupom?")

    def _fiscal_falha(self, venda_id: int, status: str):
        # venda continua válida; fiscal fica pendente/erro no banco (M6)
        self._perguntar_impressao(
            venda_id,
            f"Venda salva (fiscal: {status}). Deseja imprimir o cupom?")

    def _perguntar_impressao(self, venda_id: int, texto: str):
        if QMessageBox.question(self, "Cupom", texto) != QMessageBox.Yes:
            return
        try:
            from database.connection import get_db_path
            from services.impressao import imprimir_cupom_venda
            ok, msg = imprimir_cupom_venda(get_db_path(), venda_id)
        except Exception as e:
            QMessageBox.critical(self, "Impressão", f"Erro: {e}")
            return
        if ok:
            QMessageBox.information(self, "Impressão", msg)
        else:
            QMessageBox.warning(self, "Impressão", msg)

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
                  self.btn_rm, self.btn_limpar, self.btn_fim):
            w.setEnabled(on)
