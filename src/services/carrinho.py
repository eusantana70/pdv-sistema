"""Carrinho da frente de caixa (M4). Lógica pura, sem Qt — testável."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ItemCarrinho:
    id_produto: int
    nome: str
    codigo_interno: str
    quantidade: float
    valor_unitario: float
    subtotal: float = field(init=False)

    def __post_init__(self):
        if self.quantidade <= 0:
            raise ValueError("Quantidade deve ser > 0.")
        self.subtotal = round(self.quantidade * self.valor_unitario, 2)


class Carrinho:
    def __init__(self):
        self.itens: list = []

    def adicionar(self, produto: dict, quantidade: float = 1) -> ItemCarrinho:
        quantidade = float(quantidade)
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser > 0.")
        estoque = float(produto.get("quantidade_estoque", 0))
        em_carrinho = sum(i.quantidade for i in self.itens
                          if i.id_produto == produto["id"])
        if estoque < em_carrinho + quantidade:
            raise ValueError(f'Estoque insuficiente: {produto["nome"]} (tem {estoque:g}).')
        # agrupa mesmo produto
        for i in self.itens:
            if i.id_produto == produto["id"] and \
               float(i.valor_unitario) == float(produto["preco_venda"]):
                return self.alterar_quantidade(
                    self.itens.index(i), i.quantidade + quantidade)
        item = ItemCarrinho(
            id_produto=produto["id"], nome=produto["nome"],
            codigo_interno=produto["codigo_interno"], quantidade=quantidade,
            valor_unitario=float(produto["preco_venda"]))
        self.itens.append(item)
        return item

    def alterar_quantidade(self, index: int, nova_qtd: float) -> ItemCarrinho:
        if nova_qtd <= 0:
            return self.remover(index)
        item = self.itens[index]
        item.quantidade = float(nova_qtd)
        item.subtotal = round(item.quantidade * item.valor_unitario, 2)
        return item

    def remover(self, index: int):
        return self.itens.pop(index)

    def limpar(self):
        self.itens.clear()

    def total(self) -> float:
        return round(sum(i.subtotal for i in self.itens), 2)

    def vazio(self) -> bool:
        return len(self.itens) == 0

    def para_venda(self) -> list:
        return [{"id_produto": i.id_produto, "quantidade": i.quantidade,
                 "valor_unitario": i.valor_unitario} for i in self.itens]
