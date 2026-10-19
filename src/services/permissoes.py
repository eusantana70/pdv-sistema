"""Perfis de acesso e permissões do PDV.

Perfis:
- admin ..... tudo ("*")
- operador . frente de caixa, caixa, consulta de estoque/validade,
              consulta de histórico e relatórios (sem cadastro de produtos,
              sem limpar histórico, sem configurações e sem usuários)
"""

from __future__ import annotations

import hashlib
import hmac
import os

PERMISSOES: list[dict] = [
    {"chave": "vendas", "rotulo": "Frente de caixa (vender e receber)"},
    {"chave": "caixa", "rotulo": "Caixa (abrir, fechar, sangria, suprimento)"},
    {"chave": "estoque_consulta", "rotulo": "Consultar estoque (quantidades)"},
    {"chave": "estoque_validade", "rotulo": "Consultar validade dos produtos"},
    {"chave": "historico_consulta", "rotulo": "Consultar histórico de vendas"},
    {"chave": "relatorios", "rotulo": "Consultar relatórios de vendas"},
    {"chave": "historico_limpar", "rotulo": "Limpar histórico de vendas"},
    {"chave": "estoque_cadastro", "rotulo": "Cadastrar / editar / excluir produtos"},
    {"chave": "configuracoes", "rotulo": "Alterar configurações do sistema"},
    {"chave": "usuarios", "rotulo": "Gerenciar pessoas e acessos"},
]

PERFIS: dict[str, dict] = {
    "admin": {
        "id": "admin",
        "rotulo": "Administrador",
        "descricao": "Acesso total a todas as telas e configurações.",
        "permissoes": ["*"],
    },
    "operador": {
        "id": "operador",
        "rotulo": "Operador de caixa",
        "descricao": ("Vende, opera o caixa e consulta estoque/validade. "
                      "Não cadastra produtos, não limpa histórico e não altera configurações."),
        "permissoes": [
            "vendas", "caixa", "estoque_consulta", "estoque_validade",
            "historico_consulta", "relatorios",
        ],
    },
}


def lista_perfis() -> list:
    return [
        {**PERFIS[k], "permissoes": list(v["permissoes"])}
        for k, v in PERFIS.items()
    ]


def permissoes_de(perfil: str) -> list[str]:
    p = PERFIS.get(perfil or "operador")
    return list(p["permissoes"]) if p else list(PERFIS["operador"]["permissoes"])


def pode(perfil: str, chave: str) -> bool:
    perms = permissoes_de(perfil)
    return "*" in perms or chave in perms


# ---------- senha (pbkdf2-sha256, stdlib) ----------

_ITERACOES = 120_000


def hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", (senha or "").encode(), sal, _ITERACOES)
    return f"pbkdf2${_ITERACOES}${sal.hex()}${dk.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        alg, it, sal_hex, dk_hex = (guardado or "").split("$")
        if alg != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", (senha or "").encode(),
                                 bytes.fromhex(sal_hex), int(it))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False