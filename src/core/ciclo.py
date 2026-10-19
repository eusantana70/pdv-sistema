"""Sinal de encerramento entre a API e o pdv_main.py.

Usa um arquivo sentinela em vez de um threading.Event de propósito: dentro do
.exe empacotado o mesmo arquivo pode acabar importado sob dois nomes (ex.:
`ciclo` e `src.ciclo`), e aí cada cópia teria seu próprio Event — o botão
"Sair" não encerraria nada. No disco não existe esse problema.
"""

from __future__ import annotations

import time
from pathlib import Path


def _flag() -> Path:
    try:
        from core.paths import data_dir
    except ImportError:
        from src.core.paths import data_dir
    return data_dir() / "encerrar.flag"


def pedir_encerramento() -> None:
    """Chamado pelo botão 'Sair do sistema' (POST /api/sistema/encerrar)."""
    try:
        _flag().write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def aguardando_encerramento() -> bool:
    return _flag().exists()


def limpar() -> None:
    """Apaga o pedido anterior (um flag que sobrou de uma queda não vale)."""
    try:
        _flag().unlink(missing_ok=True)
    except Exception:
        pass


def esperar_encerramento(timeout: float | None = None) -> bool:
    """Bloqueia até alguém pedir o desligamento (o loop principal usa isso)."""
    fim = None if timeout is None else time.time() + timeout
    while True:
        if aguardando_encerramento():
            return True
        if fim is not None and time.time() >= fim:
            return False
        time.sleep(0.3)