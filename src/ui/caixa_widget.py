"""Controle de Caixa (M3): botões grandes ABRIR/FECHAR/SANGRIA/SUPRIMENTO."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from database.connection import connect
from database import repositories as repo


class CaixaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mov_aberto: dict | None = None
        self._build()
        self.recarregar()

    def _build(self):
        lay = QVBoxLayout(self)

        self.lbl_status = QLabel("...")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 16px; "
            "background: #313244; border-radius: 12px;")
        lay.addWidget(self.lbl_status)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.btn_abrir = QPushButton("ABRIR CAIXA")
        self.btn_fechar = QPushButton("FECHAR CAIXA")
        self.btn_sangria = QPushButton("SANGRIA")
        self.btn_suprimento = QPushButton("SUPRIMENTO")
        for b in (self.btn_abrir, self.btn_fechar, self.btn_sangria, self.btn_suprimento):
            b.setMinimumHeight(76)
            b.setStyleSheet("font-size: 20px;")
        self.btn_abrir.setStyleSheet("font-size: 20px; background: #2f9e44;")
        self.btn_fechar.setStyleSheet("font-size: 20px; background: #e8590c;")
        self.btn_sangria.setStyleSheet("font-size: 20px; background: #e03131;")
        self.btn_suprimento.setStyleSheet("font-size: 20px; background: #1971c2;")
        self.btn_abrir.clicked.connect(self.abrir)
        self.btn_fechar.clicked.connect(self.fechar)
        self.btn_sangria.clicked.connect(lambda: self._operacao("sangria"))
        self.btn_suprimento.clicked.connect(lambda: self._operacao("suprimento"))
        grid.addWidget(self.btn_abrir, 0, 0)
        grid.addWidget(self.btn_fechar, 0, 1)
        grid.addWidget(self.btn_sangria, 1, 0)
        grid.addWidget(self.btn_suprimento, 1, 1)
        lay.addLayout(grid)

        lay.addWidget(QLabel("Operações do caixa atual:"))
        self.tb_ops = QTableWidget(0, 5)
        self.tb_ops.setHorizontalHeaderLabels(["ID", "Tipo", "Valor R$", "Data/Hora", "Obs"])
        self.tb_ops.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb_ops.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb_ops.setAlternatingRowColors(True)
        self.tb_ops.verticalHeader().setVisible(False)
        self.tb_ops.verticalHeader().setDefaultSectionSize(32)
        lay.addWidget(self.tb_ops)

        lay.addWidget(QLabel("Histórico de movimentos:"))
        self.tb_movs = QTableWidget(0, 6)
        self.tb_movs.setHorizontalHeaderLabels(
            ["ID", "Abertura", "Fechamento", "Inicial R$", "Final R$", "Status"])
        self.tb_movs.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tb_movs.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb_movs.setAlternatingRowColors(True)
        self.tb_movs.verticalHeader().setVisible(False)
        self.tb_movs.verticalHeader().setDefaultSectionSize(32)
        lay.addWidget(self.tb_movs)

    # ----- ações -----
    def abrir(self):
        valor, ok = QInputDialog.getDouble(self, "Abrir caixa", "Valor inicial R$:", 0, 0, 1e9, 2)
        if not ok:
            return
        conn = connect()
        try:
            repo.abrir_caixa(conn, valor)
        except ValueError as e:
            QMessageBox.warning(self, "Caixa", str(e))
        finally:
            conn.close()
        self.recarregar()

    def fechar(self):
        if not self._mov_aberto:
            QMessageBox.information(self, "Caixa", "Nenhum caixa aberto.")
            return
        conn = connect()
        try:
            previsto = repo.saldo_previsto_caixa(conn, self._mov_aberto["id"])
        finally:
            conn.close()
        valor, ok = QInputDialog.getDouble(
            self, "Fechar caixa", f"Valor final R$ (previsto: {previsto:.2f}):",
            previsto, 0, 1e9, 2)
        if not ok:
            return
        conn = connect()
        try:
            repo.fechar_caixa(conn, self._mov_aberto["id"], valor)
            QMessageBox.information(self, "Caixa", "Caixa fechado.")
        except ValueError as e:
            QMessageBox.warning(self, "Caixa", str(e))
        finally:
            conn.close()
        self.recarregar()

    def _operacao(self, tipo: str):
        if not self._mov_aberto:
            QMessageBox.information(self, "Caixa", "Abra o caixa primeiro.")
            return
        valor, ok = QInputDialog.getDouble(
            self, tipo.capitalize(), f"Valor da {tipo} R$:", 0, 0.01, 1e9, 2)
        if not ok:
            return
        obs, _ = QInputDialog.getText(self, tipo.capitalize(), "Observação (opcional):")
        conn = connect()
        try:
            repo.adicionar_operacao(conn, self._mov_aberto["id"], tipo, valor, obs)
        except ValueError as e:
            QMessageBox.warning(self, "Caixa", str(e))
        finally:
            conn.close()
        self.recarregar()

    def recarregar(self):
        conn = connect()
        try:
            self._mov_aberto = repo.obter_caixa_aberto(conn)
            movs = repo.listar_movimentos(conn)
            ops = repo.listar_operacoes(conn, self._mov_aberto["id"]) if self._mov_aberto else []
            previsto = repo.saldo_previsto_caixa(conn, self._mov_aberto["id"]) \
                if self._mov_aberto else 0
        finally:
            conn.close()
        if self._mov_aberto:
            m = self._mov_aberto
            self.lbl_status.setText(
                f'CAIXA ABERTO  •  #{m["id"]} desde {m["data_abertura"]}  •  '
                f'Inicial R$ {float(m["valor_inicial"]):.2f}  •  Previsto R$ {previsto:.2f}')
            self.lbl_status.setStyleSheet(
                "font-size: 20px; font-weight: bold; padding: 16px; "
                "background: #a6e3a1; color: #11111b; border-radius: 12px;")
        else:
            self.lbl_status.setText("CAIXA FECHADO — abra para vender")
            self.lbl_status.setStyleSheet(
                "font-size: 20px; font-weight: bold; padding: 16px; "
                "background: #f38ba8; color: #11111b; border-radius: 12px;")
        tem = self._mov_aberto is not None
        self.btn_abrir.setEnabled(not tem)
        self.btn_fechar.setEnabled(tem)
        self.btn_sangria.setEnabled(tem)
        self.btn_suprimento.setEnabled(tem)

        self.tb_ops.setRowCount(len(ops))
        for r, o in enumerate(ops):
            for c, v in enumerate([o["id"], o["tipo"], f'{float(o["valor"]):.2f}',
                                   o["data_hora"], o["observacao"] or ""]):
                self.tb_ops.setItem(r, c, QTableWidgetItem(str(v)))
        self.tb_movs.setRowCount(len(movs))
        for r, m in enumerate(movs):
            for c, v in enumerate([m["id"], m["data_abertura"], m["data_fechamento"] or "-",
                                   f'{float(m["valor_inicial"]):.2f}',
                                   "-" if m["valor_final"] is None else f'{float(m["valor_final"]):.2f}',
                                   m["status"]]):
                self.tb_movs.setItem(r, c, QTableWidgetItem(str(v)))

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar()
