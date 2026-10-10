-- Esquema SQLite do PDV Sorvetes (franquia MG)
-- Arquivo único local: data/pdv.db
-- Gerado via scripts/init_db.py (stdlib sqlite3, sem dependências externas)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS perfis_fiscais (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_perfil TEXT NOT NULL UNIQUE,
    ncm         TEXT NOT NULL,
    cfop        TEXT NOT NULL DEFAULT '5102',
    csosn       TEXT NOT NULL,
    origem      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT NOT NULL,
    codigo_interno    TEXT NOT NULL UNIQUE, -- 4 dígitos aleatórios únicos gerados no backend
    ean               TEXT NOT NULL DEFAULT 'SEM GTIN',
    preco_venda       REAL NOT NULL CHECK (preco_venda >= 0),
    quantidade_estoque REAL NOT NULL DEFAULT 0,
    unidade_medida    TEXT NOT NULL DEFAULT 'UN',
    id_perfil_fiscal  INTEGER REFERENCES perfis_fiscais(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome);
CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_interno);

CREATE TABLE IF NOT EXISTS caixa_movimento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data_abertura   TEXT NOT NULL,  -- ISO8601 local
    data_fechamento TEXT,
    valor_inicial   REAL NOT NULL DEFAULT 0,
    valor_final     REAL,
    status          TEXT NOT NULL DEFAULT 'aberto' CHECK (status IN ('aberto','fechado'))
);

CREATE TABLE IF NOT EXISTS caixa_operacoes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_movimento INTEGER NOT NULL REFERENCES caixa_movimento(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL CHECK (tipo IN ('sangria','suprimento')),
    valor        REAL NOT NULL CHECK (valor > 0),
    data_hora    TEXT NOT NULL,
    observacao   TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_caixa_ops_mov ON caixa_operacoes(id_movimento);

CREATE TABLE IF NOT EXISTS vendas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_movimento   INTEGER REFERENCES caixa_movimento(id) ON DELETE SET NULL,
    total          REAL NOT NULL CHECK (total >= 0),
    data_hora      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'concluída' CHECK (status IN ('concluída','cancelada')),
    nfe_status     TEXT DEFAULT 'pendente', -- pendente | autorizado | erro | cancelado
    nfe_link_cupom TEXT DEFAULT '',
    nfe_xml        TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_hora);

CREATE TABLE IF NOT EXISTS vendas_itens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venda      INTEGER NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    id_produto    INTEGER REFERENCES produtos(id) ON DELETE SET NULL,
    quantidade    REAL NOT NULL CHECK (quantidade > 0),
    valor_unitario REAL NOT NULL CHECK (valor_unitario >= 0),
    subtotal      REAL NOT NULL CHECK (subtotal >= 0)
);
CREATE INDEX IF NOT EXISTS idx_itens_venda ON vendas_itens(id_venda);

CREATE TABLE IF NOT EXISTS vendas_pagamentos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venda INTEGER NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    metodo  TEXT NOT NULL CHECK (metodo IN ('dinheiro','credito','debito','pix')),
    valor   REAL NOT NULL CHECK (valor > 0),
    parcelas INTEGER NOT NULL DEFAULT 1 CHECK (parcelas BETWEEN 1 AND 12)
);
CREATE INDEX IF NOT EXISTS idx_pag_venda ON vendas_pagamentos(id_venda);

CREATE TABLE IF NOT EXISTS configuracoes (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    api_nfce_token TEXT DEFAULT '',
    api_nfce_url   TEXT DEFAULT '',
    impressora_nome TEXT DEFAULT ''
);

-- Linha única de configuração (upsert no init)
INSERT INTO configuracoes (id, api_nfce_token, api_nfce_url, impressora_nome)
SELECT 1, '', '', ''
WHERE NOT EXISTS (SELECT 1 FROM configuracoes WHERE id = 1);
