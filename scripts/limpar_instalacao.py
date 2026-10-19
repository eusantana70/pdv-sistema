"""Zera o PDV: apaga histórico, cadastros e todo campo preenchido.

Deixa o banco como uma instalação nova — sem vendas, sem caixa, sem produtos,
sem usuários e com a empresa em branco — para o assistente de primeiro acesso
aparecer de novo.

Uso:
    python scripts\\limpar_instalacao.py            # pede confirmação
    python scripts\\limpar_instalacao.py --sim      # sem perguntar
    python scripts\\limpar_instalacao.py --caminho D:\\outro\\pdv.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for _p in (RAIZ / "src", RAIZ):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.paths import caminho_db  # noqa: E402
from database.schema import init_db  # noqa: E402

# Ordem importa: filhos antes dos pais por causa do ON DELETE.
TABELAS = [
    "sessoes",
    "vendas_pagamentos",
    "vendas_itens",
    "vendas",
    "caixa_operacoes",
    "caixa_movimento",
    "produto_lotes",
    "produtos",
    "perfis_fiscais",
    "usuarios",
]

# Campos de configuração que o usuário pode preencher. Voltam para branco —
# menos os de comportamento (impressão, desconto, ambiente), que são padrão
# de fábrica e não contêm dado de ninguém.
CAMPOS_LIVRES = [
    "razao_social", "nome_fantasia", "cnpj", "ie", "email", "telefone",
    "endereco", "cidade_uf", "cep",
    "nuvem_token", "nuvem_url", "focus_token", "focus_url",
    "custom_token", "custom_url",
    "sefaz_cert_path", "sefaz_cert_senha",
    "recibo_qrcode_link", "recibo_titulo",
    "api_nfce_token", "api_nfce_url", "impressora_nome",
]
CAMPOS_NUMERICOS_LIVRES = ["recibo_tributos_federal", "recibo_tributos_estadual"]


def limpar(db_path: Path) -> dict:
    init_db(db_path)
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    removidos: dict[str, int] = {}
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        existentes = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for t in TABELAS:
            if t not in existentes:
                continue
            total = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            conn.execute(f"DELETE FROM {t}")
            removidos[t] = int(total)
        for t in ("produtos", "vendas", "caixa_movimento", "usuarios", "sessoes"):
            if t in existentes:
                conn.execute(f"DELETE FROM sqlite_sequence WHERE name = ?", (t,))

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(configuracoes)")}
        for c in CAMPOS_LIVRES:
            if c in cols:
                conn.execute(f"UPDATE configuracoes SET {c} = '' WHERE id = 1")
        for c in CAMPOS_NUMERICOS_LIVRES:
            if c in cols:
                conn.execute(f"UPDATE configuracoes SET {c} = 0 WHERE id = 1")
        # a coluna nova do wizard também precisa ser zerada
        if "setup_concluido_em" in cols:
            conn.execute("UPDATE configuracoes SET setup_concluido_em = '' WHERE id = 1")
        if "desconto_tipo" in cols:
            conn.execute("UPDATE configuracoes SET desconto_tipo = 'nenhum', desconto_valor = 0 WHERE id = 1")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        conn.close()
    return removidos


def main() -> int:
    ap = argparse.ArgumentParser(description="Zera o PDV (histórico + campos preenchidos).")
    ap.add_argument("--caminho", default="", help="caminho do .db (padrão: o do sistema)")
    ap.add_argument("--sim", action="store_true", help="não pedir confirmação")
    args = ap.parse_args()

    db = Path(args.caminho) if args.caminho else caminho_db()
    if not db.exists():
        print(f"Banco ainda não existe: {db}")
        print("Nada a limpar — a próxima abertura já cria um sistema zerado.")
        return 0

    print(f"Banco: {db}")
    if not args.sim:
        try:
            resp = input("Isso apaga vendas, caixa, produtos, usuários e todo campo "
                         "preenchido. Continuar? [digite ZERAR]: ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado.")
            return 1
        if resp.strip().upper() != "ZERAR":
            print("Cancelado.")
            return 1

    removidos = limpar(db)
    print("\nRegistros apagados:")
    for t, n in removidos.items():
        print(f"  {t:<22} {n}")
    print("\nCampos de configuraçãovoltaram para branco.")
    print("Abra o PDV: o assistente de configuração inicial aparecerá de novo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())