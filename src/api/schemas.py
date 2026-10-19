"""Schemas Pydantic da API — espelham o que o front Lumina consome."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ProdutoIn(BaseModel):
    nome: str
    preco_venda: float = Field(ge=0)
    quantidade_estoque: float = Field(default=0, ge=0)
    ean: str = ""  # opcional: vazio gera código aleatório único no backend
    unidade_medida: str = "UN"
    id_perfil_fiscal: int | None = None
    categoria: str = "Alimentos"
    cor: str = "green"
    validade: str = ""  # YYYY-MM-DD ou "" = indeterminada


class ProdutoPatch(BaseModel):
    nome: str | None = None
    preco_venda: float | None = Field(default=None, ge=0)
    quantidade_estoque: float | None = Field(default=None, ge=0)
    ean: str | None = None
    unidade_medida: str | None = None
    id_perfil_fiscal: int | None = None
    categoria: str | None = None
    cor: str | None = None
    validade: str | None = None


class PerfilIn(BaseModel):
    nome: str
    ncm: str
    cfop: str = "5102"
    csosn: str = ""
    origem: str = ""


class CaixaAbrir(BaseModel):
    valor_inicial: float = Field(default=0, ge=0)


class CaixaFechar(BaseModel):
    movimento_id: int
    valor_final: float = Field(ge=0)


class CaixaOperacao(BaseModel):
    id_movimento: int
    tipo: Literal["sangria", "suprimento"]
    valor: float = Field(gt=0)
    observacao: str = ""


class VendaItem(BaseModel):
    id_produto: int
    quantidade: float = Field(gt=0)
    valor_unitario: float | None = Field(default=None, ge=0)


class VendaPagamento(BaseModel):
    metodo: Literal["dinheiro", "credito", "debito", "pix"]
    valor: float = Field(gt=0)
    parcelas: int = Field(default=1, ge=1, le=12)


class VendaIn(BaseModel):
    id_movimento: int | None = None
    itens: list[VendaItem]
    pagamentos: list[VendaPagamento]
    desconto_percentual: float = Field(default=0, ge=0, lt=100)


class ConfigIn(BaseModel):
    fiscal_provider: str | None = None
    ambiente: str | None = None
    modelo_doc: str | None = None
    serie: str | None = None
    proximo_numero: int | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    cnpj: str | None = None
    ie: str | None = None
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade_uf: str | None = None
    cep: str | None = None
    impressora_nome: str | None = None
    impressora_largura: str | None = None
    impressora_vias: int | None = None
    auto_print: int | None = None
    exibir_logo: int | None = None
    corte_auto: int | None = None
    mock_url: str | None = None
    nuvem_token: str | None = None
    nuvem_url: str | None = None
    focus_token: str | None = None
    focus_url: str | None = None
    custom_token: str | None = None
    custom_url: str | None = None
    sefaz_cert_path: str | None = None
    sefaz_cert_senha: str | None = None
    api_nfce_token: str | None = None
    api_nfce_url: str | None = None
    desconto_tipo: str | None = None
    desconto_valor: float | None = None
    # nota não fiscal (comprovante)
    recibo_titulo: str | None = None
    recibo_subtitulo: str | None = None
    recibo_rodape: str | None = None
    recibo_largura: str | None = None
    recibo_mostrar_cnpj: int | None = None
    recibo_mostrar_itens: int | None = None
    recibo_mostrar_pagamentos: int | None = None
    recibo_mostrar_troco: int | None = None
    recibo_mostrar_atendente: int | None = None
    recibo_mostrar_qrcode: int | None = None
    imprimir_cupom_fiscal: int | None = None
    imprimir_cupom_nao_fiscal: int | None = None
    recibo_qrcode_link: str | None = None
    recibo_tributos_federal: float | None = None
    recibo_tributos_estadual: float | None = None
    recibo_aviso_trocas: str | None = None
    recibo_mostrar_tributos: int | None = None
    recibo_mostrar_aviso_trocas: int | None = None


class LoteIn(BaseModel):
    validade: str
    quantidade: float = Field(gt=0)


class LotesIn(BaseModel):
    lotes: list[LoteIn] = []


class LimpezaIn(BaseModel):
    inicio: str = ""
    fim: str = ""
