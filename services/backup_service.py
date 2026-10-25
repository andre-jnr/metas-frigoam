"""Exportação e importação de todo o banco local (SQLite) em JSON, para levar setores,
grupos/subgrupos e metas de uma instalação para outra sem recadastrar nada.

O backup cobre todas as filiais de uma vez. A importação SUBSTITUI o conteúdo atual:
apaga tudo e regrava com os mesmos ids do arquivo (as metas e os vínculos de grupo
referenciam setores pelo id), dentro de uma única transação — se qualquer linha for
inválida, nada é alterado."""

import sqlite3
from datetime import datetime

from database.sqlite import get_connection
from services.errors import ValidationError

FORMATO = "dashboard_metas_backup"
VERSAO = 1

# Ordem importa: pais antes dos filhos na inserção (e o inverso na exclusão).
# Para cada tabela, as colunas exportadas; as obrigatórias não podem faltar no arquivo,
# as demais caem no DEFAULT da tabela quando ausentes (backups de versões antigas).
TABELAS = {
    "setores": {
        "colunas": ["id", "nome", "descricao", "ativo", "ordem_exibicao", "pdv_incluidos", "pdv_excluidos",
                    "dias_semana_excluidos", "filial_id", "created_at", "updated_at"],
        "obrigatorias": ["id", "nome"],
    },
    "setor_grupo": {
        "colunas": ["id", "setor_id", "grupo_codigo", "created_at"],
        "obrigatorias": ["setor_id", "grupo_codigo"],
    },
    "setor_subgrupo": {
        "colunas": ["id", "setor_id", "grupo_codigo", "subgrupo_codigo", "created_at"],
        "obrigatorias": ["setor_id", "grupo_codigo", "subgrupo_codigo"],
    },
    "metas": {
        "colunas": ["id", "setor_id", "ano", "mes", "tipo_meta", "percentual_meta", "valor_meta",
                    "base_comparacao", "ativo", "created_at", "updated_at"],
        "obrigatorias": ["setor_id", "ano", "mes", "tipo_meta", "base_comparacao"],
    },
    "app_config": {
        "colunas": ["chave", "valor"],
        "obrigatorias": ["chave"],
    },
}


def exportar() -> dict:
    dados = {}
    with get_connection() as conn:
        for tabela, spec in TABELAS.items():
            rows = conn.execute(f"SELECT {', '.join(spec['colunas'])} FROM {tabela}").fetchall()
            dados[tabela] = [dict(row) for row in rows]
    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
        "dados": dados,
    }


def _validar_estrutura(backup) -> dict:
    if not isinstance(backup, dict) or backup.get("formato") != FORMATO:
        raise ValidationError("Arquivo inválido: não é um backup do sistema de metas.")
    if not isinstance(backup.get("versao"), int) or backup["versao"] > VERSAO:
        raise ValidationError("Versão do backup não suportada. Atualize o sistema antes de importar.")
    dados = backup.get("dados")
    if not isinstance(dados, dict):
        raise ValidationError("Arquivo inválido: seção 'dados' ausente.")
    for tabela, spec in TABELAS.items():
        linhas = dados.get(tabela, [])
        if not isinstance(linhas, list):
            raise ValidationError(f"Arquivo inválido: '{tabela}' deveria ser uma lista.")
        for i, linha in enumerate(linhas, start=1):
            if not isinstance(linha, dict):
                raise ValidationError(f"Arquivo inválido: registro {i} de '{tabela}' malformado.")
            faltando = [c for c in spec["obrigatorias"] if linha.get(c) is None]
            if faltando:
                raise ValidationError(
                    f"Arquivo inválido: registro {i} de '{tabela}' sem o(s) campo(s) {', '.join(faltando)}."
                )
    return dados


def importar(backup) -> dict:
    dados = _validar_estrutura(backup)
    resumo = {}
    try:
        with get_connection() as conn:
            for tabela in reversed(list(TABELAS)):
                conn.execute(f"DELETE FROM {tabela}")
            for tabela, spec in TABELAS.items():
                linhas = dados.get(tabela, [])
                for linha in linhas:
                    colunas = [c for c in spec["colunas"] if c in linha]
                    conn.execute(
                        f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})",
                        [linha[c] for c in colunas],
                    )
                resumo[tabela] = len(linhas)
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Backup com dados inconsistentes, nada foi importado ({exc}).")
    return resumo
