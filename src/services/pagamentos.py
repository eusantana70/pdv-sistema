"""Lógica de split de pagamento (Módulo 5). Sem dependências externas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PagamentoParcial:
    metodo: str  # dinheiro | credito | debito | pix
    valor: float
    parcelas: int = 1


@dataclass
class SplitPagamento:
    total: float
    partes: list = field(default_factory=list)

    def adicionar(self, metodo: str, valor: float, parcelas: int = 1) -> float:
        """Adiciona parte e retorna o saldo restante (pode ser negativo = troco)."""
        if valor <= 0:
            raise ValueError("Valor deve ser maior que zero.")
        if metodo == "credito" and not (1 <= parcelas <= 12):
            raise ValueError("Parcelas do crédito: 1 a 12.")
        if metodo != "credito":
            parcelas = 1
        self.partes.append(PagamentoParcial(metodo, round(valor, 2), parcelas))
        return self.saldo_restante()

    def pago(self) -> float:
        return round(sum(p.valor for p in self.partes), 2)

    def saldo_restante(self) -> float:
        """Positivo = falta pagar. Negativo = troco (só válido se excedente em dinheiro)."""
        return round(self.total - self.pago(), 2)

    def troco(self) -> float:
        saldo = self.saldo_restante()
        return round(-saldo, 2) if saldo < 0 else 0.0

    def concluido(self) -> bool:
        return self.saldo_restante() <= 0
