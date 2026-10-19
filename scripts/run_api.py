"""Sobe a API FastAPI do PDV Lumina (http://localhost:8000).

Uso pelo RODAR_PDV.bat. Fica em loop: se a API cair, sobe de novo em
automatico (o PDV nunca fica com "HTTP 500/502" por API morta).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.app import create_app, registrar  # noqa: E402

app = create_app()

HOST = "127.0.0.1"
PORTA = 8000


def _saude() -> bool:
    """True se já existe uma API respondendo na porta (outro supervisor rodando)."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORTA}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    cmd = [sys.executable, "-m", "uvicorn", "src.api.app:app",
           "--host", HOST, "--port", str(PORTA), "--log-level", "info"]
    registrar("supervisor: iniciado")
    while True:
        if _saude():
            # ja tem API no ar (outro supervisor): nao disputa a porta, so espera
            registrar("supervisor: ja existe API na porta 8000; aguardando")
            time.sleep(5)
            continue
        proc = subprocess.run(cmd, cwd=str(ROOT))
        registrar(f"supervisor: API saiu com codigo {proc.returncode}; subindo de novo em 3s")
        time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())