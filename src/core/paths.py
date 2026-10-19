"""Caminhos da aplicação — funciona igual no código-fonte e no .exe congelado.

Regras:
- RECURSOS (somente leitura): `_internal/` dentro do pacote do PyInstaller,
  ou a raiz do projeto quando roda de código-fonte.
- DADOS (leitura/escrita): SEMPRE na pasta do usuário (%LOCALAPPDATA%\\PDV Lumina),
  nunca ao lado do .exe — o instalador pode ir para Program Files (read-only)
  e o banco precisa sobreviver a atualizações/desinstalações do programa.

Fora do Windows cai para ~/.pdv-lumina (útil em teste/CI).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Nome da pasta do usuário e do mutex de instância única.
# Local\ (e não Global\) de propósito: Global\ exige privilégio de administrador
# e quebraria a instalação sem elevação.
APP_NOME = "PDV Lumina"
APP_SLUG = "pdv-lumina"
MUTEX = "Local\\PDVLuminaMutex"

# True quando empacotado pelo PyInstaller.
CONGELADO = bool(getattr(sys, "frozen", False))


def _raiz_recursos() -> Path:
    """Pasta dos arquivos que só o programa lê (nunca gravados)."""
    if CONGELADO:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _base_usuario() -> Path:
    """Pasta gravável do usuário em qualquer sistema."""
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if local:
        return Path(local)
    return Path.home() / ("AppData" / "Local" if sys.platform == "win32" else ".local" / "share")


def data_dir() -> Path:
    """Pasta de dados do usuário. Cria se não existir."""
    pasta = _base_usuario() / APP_NOME
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError:
        pasta = Path.home() / APP_SLUG
        pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_db() -> Path:
    """Arquivo SQLite do PDV.

    Instalado (.exe): %LOCALAPPDATA%\\PDV Lumina\\pdv.db.
    Em desenvolvimento: data/pdv.db na raiz do projeto, como sempre foi —
    assim o banco de testes/desenvolvimento não migra de lugar do nada.
    """
    override = os.environ.get("PDV_DB_PATH")
    if override:
        return Path(override)
    if not CONGELADO:
        return _raiz_recursos() / "data" / "pdv.db"
    return data_dir() / "pdv.db"


def caminho_log(nome: str = "pdv.log") -> Path:
    if not CONGELADO:
        pasta = _raiz_recursos() / "data"
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return pasta / nome
    return data_dir() / nome


def caminho_web() -> Path:
    """Pasta do frontend buildado (dist). Vazio se não existir (modo dev)."""
    candidatos = [
        _raiz_recursos() / "web",
        _raiz_recursos() / "frontend" / "dist",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    ]
    for c in candidatos:
        if (c / "index.html").is_file():
            return c
    return candidatos[0]


def caminho_recurso(relativo: str) -> Path:
    """Arquivo de recurso (schema.sql e afins) tanto no dev quanto no .exe."""
    return _raiz_recursos() / "src" / relativo