"""DDL das tabelas de configuração local (SQLite)."""

DDL_SETORES = """
CREATE TABLE IF NOT EXISTS setores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    ordem_exibicao INTEGER NOT NULL DEFAULT 0,
    pdv_incluidos TEXT,
    pdv_excluidos TEXT,
    dias_semana_excluidos TEXT,
    filial_id TEXT NOT NULL DEFAULT 'pn',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(filial_id, nome)
);
"""

DDL_APP_CONFIG = """
CREATE TABLE IF NOT EXISTS app_config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Migração idempotente: bancos criados antes destes campos existirem ganham as colunas aqui.
# dias_semana_excluidos usa 0=Segunda ... 6=Domingo (mesma convenção de date.weekday() do Python
# e de DATEDIFF(day, 0, Data) % 7 no SQL Server, já que 1900-01-01 foi uma segunda-feira).
MIGRACOES_SETORES = [
    "ALTER TABLE setores ADD COLUMN pdv_incluidos TEXT",
    "ALTER TABLE setores ADD COLUMN pdv_excluidos TEXT",
    "ALTER TABLE setores ADD COLUMN dias_semana_excluidos TEXT",
]

DDL_SETOR_GRUPO = """
CREATE TABLE IF NOT EXISTS setor_grupo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setor_id INTEGER NOT NULL REFERENCES setores(id) ON DELETE CASCADE,
    grupo_codigo INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(setor_id, grupo_codigo)
);
"""

DDL_SETOR_SUBGRUPO = """
CREATE TABLE IF NOT EXISTS setor_subgrupo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setor_id INTEGER NOT NULL REFERENCES setores(id) ON DELETE CASCADE,
    grupo_codigo INTEGER NOT NULL,
    subgrupo_codigo INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(setor_id, grupo_codigo, subgrupo_codigo)
);
"""

DDL_METAS = """
CREATE TABLE IF NOT EXISTS metas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setor_id INTEGER NOT NULL REFERENCES setores(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    tipo_meta TEXT NOT NULL CHECK (tipo_meta IN ('PERCENTUAL', 'VALOR_FIXO')),
    percentual_meta REAL,
    valor_meta REAL,
    base_comparacao TEXT NOT NULL CHECK (
        base_comparacao IN ('MESMO_MES_ANO_ANTERIOR', 'MES_ANTERIOR', 'NAO_APLICAVEL')
    ),
    ativo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(setor_id, ano, mes)
);
"""

DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_setor_grupo_setor ON setor_grupo(setor_id);
CREATE INDEX IF NOT EXISTS idx_setor_subgrupo_setor ON setor_subgrupo(setor_id);
CREATE INDEX IF NOT EXISTS idx_metas_periodo ON metas(ano, mes);
CREATE INDEX IF NOT EXISTS idx_metas_setor ON metas(setor_id);
"""

ALL_DDL = [DDL_SETORES, DDL_APP_CONFIG, DDL_SETOR_GRUPO, DDL_SETOR_SUBGRUPO, DDL_METAS, DDL_INDEXES]

TIPOS_META = ("PERCENTUAL", "VALOR_FIXO")
BASES_COMPARACAO = ("MESMO_MES_ANO_ANTERIOR", "MES_ANTERIOR", "NAO_APLICAVEL")
