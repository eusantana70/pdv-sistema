"""Gerencia os usuarios do PDV (listar / recriar acesso de administrador).

Nao existe mais senha padrao: a senha do administrador e definida por voce
no assistente de primeiro acesso. Este script existe para quando alguem
perde a senha do unico administrador.

Uso:
  python scripts\\reset_usuarios.py --listar
  python scripts\\reset_usuarios.py --senha "NovaSenha123" --login admin
  python scripts\\reset_usuarios.py --zerar      # apaga todos os usuarios
                                                 # (o assistente volta a aparecer)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database.connection import connect, get_db_path  # noqa: E402
from database import repositories as repo  # noqa: E402
from database.schema import init_db  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Usuarios do PDV Lumina.")
    ap.add_argument("--listar", action="store_true", help="apenas lista os usuarios")
    ap.add_argument("--zerar", action="store_true",
                    help="apaga todos os usuarios (o assistente inicial reaparece)")
    ap.add_argument("--login", default="admin", help="login do novo administrador")
    ap.add_argument("--senha", default="", help="senha do novo administrador")
    ap.add_argument("--nome", default="Administrador")
    args = ap.parse_args()

    init_db()
    conn = connect(get_db_path())
    try:
        if args.listar:
            usuarios = repo.listar_usuarios(conn)
            if not usuarios:
                print("Nenhum usuario cadastrado (o assistente inicial vai aparecer).")
            for u in usuarios:
                print(f"id={u['id']:>3}  {u['login']:<14} {u['perfil']:<9} "
                      f"ativo={u['ativo']}  {u['nome']}")
            return 0

        if args.zerar:
            if not args.listar:
                resp = input("Isso apaga TODOS os usuarios. Confirme digitando ZERAR: ")
                if resp.strip().upper() != "ZERAR":
                    print("Cancelado.")
                    return 1
            conn.execute("DELETE FROM sessoes")
            conn.execute("DELETE FROM usuarios")
            conn.commit()
            print("Usuarios apagados. Ao abrir o PDV, o assistente de configuracao reaparece.")
            return 0

        if not args.senha:
            print("Informe a senha com --senha \"...\". (nao existe senha padrao no PDV Lumina)")
            return 1
        if len(args.senha) < 6:
            print("A senha precisa de pelo menos 6 caracteres.")
            return 1

        repo.resetar_usuarios(conn, args.nome, args.login, args.senha, "admin")
        print("Usuarios zerados e administrador recriado:")
        for u in repo.listar_usuarios(conn):
            print(f"  id={u['id']} login={u['login']} perfil={u['perfil']} ativo={u['ativo']}")
        print(f"\n  LOGIN: {args.login}")
        print(f"  SENHA: {args.senha}")
        print("\nSessoes antigas invalidadas. Troque a senha assim que entrar.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())