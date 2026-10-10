"""Histórico e relatórios (M7): vendas, cancelar c/ estorno, reimprimir, totais do dia."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from database.connection import connect, get_db_path
from database import repositories as repo


class HistoricoWidget(QWidget):
    COLS = ["ID", "Data/Hora", "Total R$", "Status", "NFe", "Mov"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self.recarregar()

    def _build(self):
        lay = QVBoxLayout(self)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Dia:"))
        self.ed_dia = QDateEdit(QDate.currentDate())
        self.ed_dia.setCalendarPopup(True)
        self.ed_dia.setDisplayFormat("dd/MM/yyyy")
        self.ed_dia.dateChanged.connect(self.recarregar)
        self.cb_status = QComboBox()
        self.cb_status.addItems(["todas", "concluída", "cancelada"])
        self.cb_status.currentTextChanged.connect(self.recarregar)
        self.btn_upd = QPushButton("Atualizar")
        self.btn_upd.clicked.connect(self.recarregar)
        filtros.addWidget(self.ed_dia)
        filtros.addWidget(QLabel("Status:"))
        filtros.addWidget(self.cb_status)
        filtros.addWidget(self.btn_upd)
        filtros.addStretch(1)
        lay.addLayout(filtros)

        self.lbl_rel = QLabel("")
        self.lbl_rel.setStyleSheet(
            "font-weight: bold; padding: 10px; background: #313244; border-radius: 8px;")
        self.lbl_rel.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_rel)

        lay.addWidget(QLabel("Vendas:"))
        self.tb = QTableWidget(0, len(self.COLS))
        self.tb.setHorizontalHeaderLabels(self.COLS)
        self.tb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb.verticalHeader().setVisible(False)
        self.tb.horizontalHeader().setStretchLastSection(True)
        self.tb.itemSelectionChanged.connect(self._detalhar)
        lay.addWidget(self.tb, 2)

        det = QHBoxLayout()
        self.tb_itens = QTableWidget(0, 4)
        self.tb_itens.setHorizontalHeaderLabels(["Produto", "Qtd", "Unit R$", "Subtotal R$"])
        self.tb_itens.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb_itens.verticalHeader().setVisible(False)
        self.tb_pags = QTableWidget(0, 3)
        self.tb_pags.setHorizontalHeaderLabels(["Método", "Parcelas", "Valor R$"])
        self.tb_pags.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb_pags.verticalHeader().setVisible(False)
        det.addWidget(self.tb_itens, 2)
        det.addWidget(self.tb_pags, 1)
        lay.addLayout(det, 1)

        acoes = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar venda (estorna estoque)")
        self.btn_cancel.clicked.connect(self.cancelar)
        self.btn_reimp = QPushButton("Reimprimir cupom")
        self.btn_reimp.clicked.connect(self.reimprimir)
        acoes.addWidget(self.btn_cancel)
        acoes.addWidget(self.btn_reimp)
        acoes.addStretch(1)
        lay.addLayout(acoes)

    # ----- dados -----
    def _dia_iso(self) -> str:
        return self.ed_dia.date().toString("yyyy-MM-dd")

    def recarregar(self):
        dia = self._dia_iso()
        status = self.cb_status.currentText()
        conn = connect()
        try:
            vendas = repo.listar_vendas(conn, dia, "" if status == "todas" else status)
            tot = repo.totais_por_pagamento(conn, dia)
        finally:
            conn.close()
        self.tb.setRowCount(len(vendas))
        for r, v in enumerate(vendas):
            for c, val in enumerate([
                    v["id"], v["data_hora"], f'{float(v["total"]):.2f}',
                    v["status"], v.get("nfe_status", ""),
                    v["id_movimento"] or "-"]):
                self.tb.setItem(r, c, QTableWidgetItem(str(val)))
        self.lbl_rel.setText(
            f'Fechamento {self.ed_dia.date().toString("dd/MM/yyyy")} — '
            f'{tot["_vendas"]} venda(s)  •  '
            f'Din R$ {tot["dinheiro"]:.2f}  •  '
            f'Créd R$ {tot["credito"]:.2f}  •  '
            f'Déb R$ {tot["debito"]:.2f}  •  '
            f'PIX R$ {tot["pix"]:.2f}  •  '
            f'TOTAL R$ {tot["_geral"]:.2f}')
        self._detalhar()

    def _venda_sel(self) -> int | None:
        row = self.tb.currentRow()
        if row < 0:
            return None
        return int(self.tb.item(row, 0).text())

    def _detalhar(self):
        vid = self._venda_sel()
        self.tb_itens.setRowCount(0)
        self.tb_pags.setRowCount(0)
        if vid is None:
            return
        conn = connect()
        try:
            itens = repo.listar_itens_venda(conn, vid)
            pags = repo.listar_pagamentos_venda(conn, vid)
        finally:
            conn.close()
        self.tb_itens.setRowCount(len(itens))
        for r, it in enumerate(itens):
            for c, val in enumerate([
                    it.get("nome") or f'Produto {it.get("id_produto")}',
                    ('%g' % float(it["quantidade"])),
                    f'{float(it["valor_unitario"]):.2f}',
                    f'{float(it["subtotal"]):.2f}']):
                self.tb_itens.setItem(r, c, QTableWidgetItem(str(val)))
        self.tb_pags.setRowCount(len(pags))
        for r, p in enumerate(pags):
            for c, val in enumerate(
                    [p["metodo"], p.get("parcelas", 1), f'{float(p["valor"]):.2f}']):
                self.tb_pags.setItem(r, c, QTableWidgetItem(str(val)))

    def cancelar(self):
        vid = self._venda_sel()
        if vid is None:
            QMessageBox.information(self, "Histórico", "Selecione uma venda.")
            return
        if QMessageBox.question(
                self, "Cancelar",
                f"Cancelar venda #{vid}? Estoque será estornado.") != QMessageBox.Yes:
            return
        conn = connect()
        try:
            repo.cancelar_venda(conn, vid)
            cfg = repo.obter_config(conn)
        except ValueError as e:
            QMessageBox.warning(self, "Histórico", str(e))
            conn.close()
            return
        finally:
            conn.close()
        from services.fiscal import tentar_cancelar
        ok_api, msg_api = tentar_cancelar(vid, cfg.get("api_nfce_token", ""),
                                          cfg.get("api_nfce_url", ""))
        QMessageBox.information(self, "Histórico", f"Venda #{vid} cancelada.\n{msg_api}")
        self.recarregar()

    def reimprimir(self):
        vid = self._venda_sel()
        if vid is None:
            QMessageBox.information(self, "Histórico", "Selecione uma venda.")
            return
        from services.impressao import imprimir_cupom_venda
        ok, msg = imprimir_cupom_venda(get_db_path(), vid)
        if ok:
            QMessageBox.information(self, "Impressão", msg)
        else:
            QMessageBox.warning(self, "Impressão", msg)

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar()
