"""Rotas de produtos + perfis — formato pronto pro front Lumina."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from pathlib import Path

from .auth import exige
from .deps import get_conn
from .schemas import LoteIn, LotesIn, ProdutoIn, ProdutoPatch, PerfilIn

router = APIRouter()


def _repo():
    try:
        from database import repositories as repo
        return repo
    except ImportError:
        from src.database import repositories as repo
        return repo


def _front(p: dict, conn=None) -> dict:
    repo = _repo()
    lotes = []
    try:
        if conn is not None and p.get("id"):
            lotes = repo.listar_lotes(conn, p["id"])
    except Exception:
        lotes = []
    return repo.produto_para_front(p, lotes)


@router.get("/produtos", dependencies=[Depends(exige("estoque_consulta"))])
def listar_produtos(busca: str = Query(default=""), conn=Depends(get_conn)):
    repo = _repo()
    return [_front(p, conn) for p in repo.listar_produtos(conn, busca)]


@router.get("/produtos/busca", dependencies=[Depends(exige("estoque_consulta"))])
def busca_pdv(termo: str = Query(default=""), limite: int = Query(default=7, le=50),
              conn=Depends(get_conn)):
    """Autocomplete da frente de caixa: nome ou 4 dígitos."""
    repo = _repo()
    rows = repo.buscar_para_pdv(conn, termo, limite if termo else 50)
    return [_front(dict(r), conn) if "nome_perfil" not in r else _front(r, conn) for r in rows]


@router.post("/produtos", status_code=201, dependencies=[Depends(exige("estoque_cadastro"))])
def criar_produto(body: ProdutoIn, conn=Depends(get_conn)):
    repo = _repo()
    try:
        p = repo.criar_produto(conn, body.nome, body.preco_venda, body.quantidade_estoque,
                               body.id_perfil_fiscal, body.ean, body.unidade_medida,
                               body.categoria, body.cor, body.validade)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _front(p, conn)


@router.post("/produtos/importar", dependencies=[Depends(exige("estoque_cadastro"))])
def importar_produtos(arquivo: UploadFile = File(...), conn=Depends(get_conn)):
    """Importa produtos a partir de CSV/TXT, XLSX, PDF ou DOCX.

    Cada linha do arquivo deve conter: nome, sku, categoria, preco, estoque,
    unidade, cor, validade (colunas opcionais exceto o nome).
    """
    from services.importacao import ler_arquivo, validar_e_normalizar
    import tempfile

    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in (".csv", ".txt", ".tsv", ".xlsx", ".xls", ".pdf", ".docx", ".doc"):
        raise HTTPException(400, f"Extensão não suportada: {extensao}. Use .csv, .txt, .xlsx, .pdf ou .docx")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=extensao)
    try:
        conteudo = arquivo.file.read()
        tmp.write(conteudo)
        tmp.close()

        try:
            linhas = ler_arquivo(tmp.name)
        except Exception as e:
            raise HTTPException(400, f"Não foi possível ler o arquivo: {e}")

        validos, erros = validar_e_normalizar(linhas)

        repo = _repo()
        importados: list[dict] = []
        erros_importacao: list[dict] = []

        for p in validos:
            try:
                criado = repo.criar_produto(
                    conn,
                    p["nome"],
                    p["preco_venda"],
                    p["quantidade_estoque"],
                    p.get("id_perfil_fiscal"),
                    p.get("sku") or None,
                    p.get("unidade_medida") or "UN",
                    p.get("categoria"),
                    p.get("cor") or "green",
                    p.get("validade") or "",
                )
                importados.append(_front(criado, conn))
            except ValueError as e:
                erros_importacao.append({"nome": p.get("nome", ""), "erro": str(e)})

        return {
            "total_enviado": len(linhas),
            "importados": len(importados),
            "produtos": importados,
            "erros_validacao": erros,
            "erros_importacao": erros_importacao,
            "total_erros": len(erros) + len(erros_importacao),
        }
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass


@router.put("/produtos/{produto_id}", dependencies=[Depends(exige("estoque_cadastro"))])
def atualizar_produto(produto_id: int, body: ProdutoPatch, conn=Depends(get_conn)):
    repo = _repo()
    atual = repo.obter_produto(conn, produto_id)
    if not atual:
        raise HTTPException(404, "Produto não encontrado.")
    try:
        repo.atualizar_produto(
            conn, produto_id,
            body.nome if body.nome is not None else atual["nome"],
            body.preco_venda if body.preco_venda is not None else atual["preco_venda"],
            body.quantidade_estoque if body.quantidade_estoque is not None else atual["quantidade_estoque"],
            body.id_perfil_fiscal if body.id_perfil_fiscal is not None else atual["id_perfil_fiscal"],
            body.ean if body.ean is not None else atual["ean"],
            body.unidade_medida if body.unidade_medida is not None else atual["unidade_medida"],
            body.categoria, body.cor, body.validade,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _front(repo.obter_produto(conn, produto_id), conn)


@router.get("/produtos/{produto_id}/lotes", dependencies=[Depends(exige("estoque_consulta"))])
def listar_lotes(produto_id: int, conn=Depends(get_conn)):
    return _repo().listar_lotes(conn, produto_id)


@router.put("/produtos/{produto_id}/lotes", dependencies=[Depends(exige("estoque_cadastro"))])
def substituir_lotes(produto_id: int, body: LotesIn, conn=Depends(get_conn)):
    repo = _repo()
    try:
        return repo.substituir_lotes(
            conn, produto_id,
            [{"validade": l.validade, "quantidade": l.quantidade} for l in body.lotes])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/produtos/lotes/{lote_id}", status_code=204, dependencies=[Depends(exige("estoque_cadastro"))])
def remover_lote(lote_id: int, conn=Depends(get_conn)):
    try:
        _repo().remover_lote(conn, lote_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return None


@router.delete("/produtos/{produto_id}", status_code=204, dependencies=[Depends(exige("estoque_cadastro"))])
def excluir_produto(produto_id: int, conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    try:
        repo.excluir_produto(conn, produto_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return None


@router.post("/produtos/{produto_id}/desconto", dependencies=[Depends(exige("estoque_cadastro"))])
def desconto_produto(produto_id: int, percentual: float, conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    try:
        novo = repo.aplicar_desconto(conn, produto_id, percentual)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": produto_id, "novo_preco": novo}


# ---- perfis fiscais ----

@router.get("/perfis", dependencies=[Depends(exige("estoque_consulta"))])
def listar_perfis(conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    return repo.listar_perfis(conn)


@router.post("/perfis", status_code=201, dependencies=[Depends(exige("estoque_cadastro"))])
def criar_perfil(body: PerfilIn, conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    try:
        pid = repo.criar_perfil(conn, body.nome, body.ncm, body.cfop, body.csosn, body.origem)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return repo.obter_perfil(conn, pid)


@router.put("/perfis/{perfil_id}", dependencies=[Depends(exige("estoque_cadastro"))])
def atualizar_perfil(perfil_id: int, body: PerfilIn, conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    try:
        repo.atualizar_perfil(conn, perfil_id, body.nome, body.ncm, body.cfop, body.csosn, body.origem)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return repo.obter_perfil(conn, perfil_id)


@router.delete("/perfis/{perfil_id}", status_code=204, dependencies=[Depends(exige("estoque_cadastro"))])
def excluir_perfil(perfil_id: int, conn=Depends(get_conn)):
    try:
        from database import repositories as repo
    except ImportError:
        from src.database import repositories as repo
    try:
        repo.excluir_perfil(conn, perfil_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return None
