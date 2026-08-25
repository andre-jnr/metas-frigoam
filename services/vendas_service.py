"""Consultas agregadas de vendas no SQL Server.

A ligação setor -> grupo mora no SQLite; aqui recebemos sempre uma lista de
`grupo_codigo`s já resolvida e construímos um IN (...) parametrizado contra o
SQL Server. Nunca fazemos JOIN entre os dois bancos.

Além do filtro por grupo de produto, um setor pode opcionalmente filtrar por
PDV (incluindo ou excluindo códigos específicos) e por dia da semana
excluído — usado por setores como "Delivery" (PDV específico, sem domingo)
que não são definidos por grupo de produto nenhum. Convenção de dia da
semana: 0=Segunda ... 6=Domingo (igual a date.weekday() no Python e a
DATEDIFF(day, 0, Data) % 7 no SQL Server, já que 1900-01-01 foi segunda-feira).
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from database.sql_server import executar_query

logger = logging.getLogger("dashboard_metas.vendas_service")

# Pseudo-código de subgrupo usado só dentro desta aplicação (nunca existe na
# tabela SubGrupo, que começa em 1) para representar produtos sem
# classificação de subgrupo válida: SubGrupo nulo, "0" (convenção do próprio
# sismoura para "não classificado") ou um código que não existe mais na
# tabela SubGrupo (subgrupo excluído no cadastro, mas ainda usado em produto).
SEM_SUBGRUPO_CODIGO = 0
SEM_SUBGRUPO_DESCRICAO = "Sem subgrupo"


def _dec(valor) -> Decimal:
    return Decimal(str(valor)) if valor is not None else Decimal("0")


def _clausula_pdv_dia(pdv_incluidos, pdv_excluidos, dias_semana_excluidos) -> tuple[str, list]:
    """Fragmentos SQL (sempre começando com AND) + params para os filtros de
    PDV e dia da semana, aplicáveis independentemente do filtro de grupo."""
    partes = []
    params: list = []

    if pdv_incluidos:
        codigos = sorted(set(pdv_incluidos))
        partes.append("v.PDV IN (" + ",".join("?" * len(codigos)) + ")")
        params.extend(codigos)

    if pdv_excluidos:
        codigos = sorted(set(pdv_excluidos))
        partes.append("v.PDV NOT IN (" + ",".join("?" * len(codigos)) + ")")
        params.extend(codigos)

    if dias_semana_excluidos:
        dias = sorted(set(dias_semana_excluidos))
        partes.append("(DATEDIFF(day, 0, v.Data) % 7) NOT IN (" + ",".join("?" * len(dias)) + ")")
        params.extend(dias)

    sql = "".join(f" AND {parte}" for parte in partes)
    return sql, params


def _tem_algum_filtro(grupo_codigos, pdv_incluidos, pdv_excluidos, dias_semana_excluidos) -> bool:
    return bool(grupo_codigos) or bool(pdv_incluidos) or bool(pdv_excluidos) or bool(dias_semana_excluidos)


def _clausula_grupo(
    grupo_codigos: list[int], subgrupos_por_grupo: dict[int, list[int]] | None = None
) -> tuple[str, list]:
    """Fragmento SQL (sempre começando com AND) + params para o filtro de
    grupo/subgrupo de produto. Grupo sem narrowing em subgrupos_por_grupo
    inclui o grupo inteiro (inclusive subgrupos futuros); grupo presente no
    mapa restringe a p.SubGrupo IN (...) só para aquele grupo.
    SEM_SUBGRUPO_CODIGO na lista de subgrupos vira uma condição própria,
    cobrindo produtos com SubGrupo nulo ou com um código que não existe (mais)
    na tabela SubGrupo — sem isso, esses produtos ficariam de fora do
    narrowing sem nenhuma forma de o usuário incluí-los de volta."""
    if not grupo_codigos:
        return "", []
    subgrupos_por_grupo = subgrupos_por_grupo or {}
    clausulas = []
    params: list = []
    for grupo in sorted(set(grupo_codigos)):
        subs = subgrupos_por_grupo.get(grupo)
        if subs:
            subs_unicos = sorted(set(subs))
            subs_reais = [s for s in subs_unicos if s != SEM_SUBGRUPO_CODIGO]
            condicoes = []
            params_grupo: list = []
            if subs_reais:
                condicoes.append("p.SubGrupo IN (" + ",".join("?" * len(subs_reais)) + ")")
                params_grupo.extend(subs_reais)
            if SEM_SUBGRUPO_CODIGO in subs_unicos:
                condicoes.append("p.SubGrupo IS NULL")
                condicoes.append("p.SubGrupo NOT IN (SELECT Codigo FROM SubGrupo)")
            clausulas.append("(p.Grupo = ? AND (" + " OR ".join(condicoes) + "))")
            params.append(grupo)
            params.extend(params_grupo)
        else:
            clausulas.append("p.Grupo = ?")
            params.append(grupo)
    sql = " AND (" + " OR ".join(clausulas) + ")"
    return sql, params


def faturamento_por_grupo(data_ini: date, data_fim: date) -> dict[int, Decimal]:
    """Uma única query agregada: faturamento de TODOS os grupos no período,
    sem nenhum filtro de PDV/dia da semana.

    Usada pelo dashboard para calcular o faturamento dos setores "simples"
    (sem filtro de PDV) de uma vez só — cada setor soma os grupos que lhe
    pertencem. Setores com filtro de PDV/dia da semana usam
    `faturamento_periodo` individualmente, pois não podem compartilhar este
    resultado agregado.
    """
    sql = """
        SELECT p.Grupo AS grupo, SUM(vi.Valor_Total) AS total
        FROM Venda_item vi
        JOIN Venda v ON v.Codigo = vi.Venda
        JOIN produto p ON p.Codigo = vi.Produto
        WHERE v.Cancelada = 'N' AND vi.Cancelado = 'N'
          AND CAST(v.Data AS DATE) BETWEEN ? AND ?
        GROUP BY p.Grupo
    """
    rows = executar_query(sql, (data_ini, data_fim))
    return {int(r["grupo"]): _dec(r["total"]) for r in rows if r["grupo"] is not None}


def somar_grupos(mapa_grupo: dict[int, Decimal], grupo_codigos: list[int]) -> Decimal:
    """Soma pura (sem I/O) dos totais de um conjunto de grupos já consultado."""
    codigos_unicos = set(grupo_codigos)
    return sum((mapa_grupo.get(codigo, Decimal("0")) for codigo in codigos_unicos), Decimal("0"))


def faturamento_periodo(
    grupo_codigos: list[int],
    data_ini: date,
    data_fim: date,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
    subgrupos_por_grupo: dict[int, list[int]] | None = None,
) -> Decimal:
    """Faturamento de um único setor num período — usado nas telas de detalhe,
    no cálculo de base de metas percentuais e nos setores "especiais" (com
    filtro de PDV/dia da semana ou de subgrupo) do dashboard.

    grupo_codigos vazio + algum filtro de PDV/dia definido = considera TODOS
    os grupos de produto (ex: Delivery). grupo_codigos vazio SEM nenhum outro
    filtro = setor ainda não configurado, retorna 0 (comportamento padrão).
    """
    codigos_unicos = sorted(set(grupo_codigos))
    if not _tem_algum_filtro(codigos_unicos, pdv_incluidos, pdv_excluidos, dias_semana_excluidos):
        return Decimal("0")

    join_produto = "JOIN produto p ON p.Codigo = vi.Produto" if codigos_unicos else ""
    filtro_grupo, params = _clausula_grupo(codigos_unicos, subgrupos_por_grupo)

    filtro_pdv_dia, params_pdv_dia = _clausula_pdv_dia(pdv_incluidos, pdv_excluidos, dias_semana_excluidos)

    sql = f"""
        SELECT SUM(vi.Valor_Total) AS total
        FROM Venda_item vi
        JOIN Venda v ON v.Codigo = vi.Venda
        {join_produto}
        WHERE v.Cancelada = 'N' AND vi.Cancelado = 'N'
          AND CAST(v.Data AS DATE) BETWEEN ? AND ?
          {filtro_grupo}
          {filtro_pdv_dia}
    """
    params_finais = [data_ini, data_fim] + params + params_pdv_dia
    rows = executar_query(sql, tuple(params_finais))
    return _dec(rows[0]["total"]) if rows else Decimal("0")


def evolucao_diaria(
    grupo_codigos: list[int],
    data_ini: date,
    data_fim: date,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
    subgrupos_por_grupo: dict[int, list[int]] | None = None,
) -> list[dict]:
    """Venda diária + acumulado dentro do intervalo, preenchendo dias sem venda
    (incluindo dias excluídos pelo filtro de dia da semana) com 0."""
    codigos_unicos = sorted(set(grupo_codigos))
    por_dia: dict[date, Decimal] = {}

    if _tem_algum_filtro(codigos_unicos, pdv_incluidos, pdv_excluidos, dias_semana_excluidos):
        join_produto = "JOIN produto p ON p.Codigo = vi.Produto" if codigos_unicos else ""
        filtro_grupo, params = _clausula_grupo(codigos_unicos, subgrupos_por_grupo)

        filtro_pdv_dia, params_pdv_dia = _clausula_pdv_dia(pdv_incluidos, pdv_excluidos, dias_semana_excluidos)

        sql = f"""
            SELECT CAST(v.Data AS DATE) AS dia, SUM(vi.Valor_Total) AS total
            FROM Venda_item vi
            JOIN Venda v ON v.Codigo = vi.Venda
            {join_produto}
            WHERE v.Cancelada = 'N' AND vi.Cancelado = 'N'
              AND CAST(v.Data AS DATE) BETWEEN ? AND ?
              {filtro_grupo}
              {filtro_pdv_dia}
            GROUP BY CAST(v.Data AS DATE)
        """
        params_finais = [data_ini, data_fim] + params + params_pdv_dia
        rows = executar_query(sql, tuple(params_finais))
        por_dia = {r["dia"]: _dec(r["total"]) for r in rows}

    resultado = []
    acumulado = Decimal("0")
    dia_cursor = data_ini
    while dia_cursor <= data_fim:
        valor_dia = por_dia.get(dia_cursor, Decimal("0"))
        acumulado += valor_dia
        resultado.append({"dia": dia_cursor.isoformat(), "valor": valor_dia, "acumulado": acumulado})
        dia_cursor += timedelta(days=1)
    return resultado


def ranking_grupos(
    grupo_codigos: list[int],
    data_ini: date,
    data_fim: date,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
    subgrupos_por_grupo: dict[int, list[int]] | None = None,
) -> list[dict]:
    """Faturamento por grupo dentro de um setor, ordenado decrescente (seção 27).
    Sempre agrupa por grupo de produto (para mostrar a composição), mesmo
    quando o setor não restringe grupos — o filtro de PDV/dia se aplica
    igualmente."""
    codigos_unicos = sorted(set(grupo_codigos))
    if not _tem_algum_filtro(codigos_unicos, pdv_incluidos, pdv_excluidos, dias_semana_excluidos):
        return []

    filtro_grupo, params = _clausula_grupo(codigos_unicos, subgrupos_por_grupo)

    filtro_pdv_dia, params_pdv_dia = _clausula_pdv_dia(pdv_incluidos, pdv_excluidos, dias_semana_excluidos)

    sql = f"""
        SELECT p.Grupo AS grupo_codigo, MAX(g.Descricao) AS descricao, SUM(vi.Valor_Total) AS total
        FROM Venda_item vi
        JOIN Venda v ON v.Codigo = vi.Venda
        JOIN produto p ON p.Codigo = vi.Produto
        LEFT JOIN Grupo_Produto g ON g.Codigo = p.Grupo
        WHERE v.Cancelada = 'N' AND vi.Cancelado = 'N'
          AND CAST(v.Data AS DATE) BETWEEN ? AND ?
          {filtro_grupo}
          {filtro_pdv_dia}
        GROUP BY p.Grupo
        ORDER BY total DESC
    """
    params_finais = [data_ini, data_fim] + params + params_pdv_dia
    rows = executar_query(sql, tuple(params_finais))
    return [
        {
            "grupo_codigo": int(r["grupo_codigo"]),
            "descricao": r["descricao"] or f"Grupo {r['grupo_codigo']}",
            "total": _dec(r["total"]),
        }
        for r in rows
    ]


METRICAS_PRODUTO = ("valor", "quantidade")


def vendas_por_produto(
    grupo_codigos: list[int],
    data_ini: date,
    data_fim: date,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
    metrica: str = "valor",
    subgrupos_por_grupo: dict[int, list[int]] | None = None,
) -> dict[int, dict]:
    """Faturamento (ou quantidade vendida) por produto individual dentro de um
    setor/período — base da tabela de detalhamento por produto. Mesmo
    tratamento de grupo_codigos vazio que as demais funções (setor "todos os
    produtos", ex: Delivery). metrica inválida cai silenciosamente em "valor"."""
    codigos_unicos = sorted(set(grupo_codigos))
    if not _tem_algum_filtro(codigos_unicos, pdv_incluidos, pdv_excluidos, dias_semana_excluidos):
        return {}

    coluna_soma = "vi.Quantidade" if metrica == "quantidade" else "vi.Valor_Total"

    filtro_grupo, params = _clausula_grupo(codigos_unicos, subgrupos_por_grupo)

    filtro_pdv_dia, params_pdv_dia = _clausula_pdv_dia(pdv_incluidos, pdv_excluidos, dias_semana_excluidos)

    sql = f"""
        SELECT p.Codigo AS codigo, MAX(p.Nome) AS nome, p.Grupo AS grupo_codigo, SUM({coluna_soma}) AS total
        FROM Venda_item vi
        JOIN Venda v ON v.Codigo = vi.Venda
        JOIN produto p ON p.Codigo = vi.Produto
        WHERE v.Cancelada = 'N' AND vi.Cancelado = 'N'
          AND CAST(v.Data AS DATE) BETWEEN ? AND ?
          {filtro_grupo}
          {filtro_pdv_dia}
        GROUP BY p.Codigo, p.Grupo
    """
    params_finais = [data_ini, data_fim] + params + params_pdv_dia
    rows = executar_query(sql, tuple(params_finais))
    return {
        int(r["codigo"]): {
            "nome": r["nome"] or f"Produto {r['codigo']}",
            "grupo_codigo": int(r["grupo_codigo"]) if r["grupo_codigo"] is not None else None,
            "total": _dec(r["total"]),
        }
        for r in rows
    }


def listar_grupos_disponiveis() -> list[dict]:
    """Todos os grupos de produto cadastrados no SQL Server, para a tela de setores."""
    sql = "SELECT Codigo AS codigo, Descricao AS descricao FROM Grupo_Produto ORDER BY Descricao"
    rows = executar_query(sql)
    return [{"codigo": int(r["codigo"]), "descricao": r["descricao"] or f"Grupo {r['codigo']}"} for r in rows]


def listar_subgrupos_disponiveis() -> list[dict]:
    """Todos os subgrupos cadastrados no SQL Server, para a tela de setores."""
    sql = "SELECT Codigo AS codigo, Descricao AS descricao FROM SubGrupo ORDER BY Descricao"
    rows = executar_query(sql)
    return [{"codigo": int(r["codigo"]), "descricao": r["descricao"] or f"Subgrupo {r['codigo']}"} for r in rows]


def listar_subgrupos_por_grupo() -> dict[int, list[dict]]:
    """Mapa grupo_codigo -> [{codigo, descricao}] dos subgrupos que de fato
    aparecem em produtos daquele grupo, com um pseudo-subgrupo "Sem subgrupo"
    (SEM_SUBGRUPO_CODIGO) inserido na frente da lista para todo grupo que
    tenha produtos sem classificação de subgrupo válida — sem essa entrada,
    esses produtos não têm como ser incluídos quando o usuário restringe o
    grupo por subgrupo (ver `_clausula_grupo`)."""
    sql_com_subgrupo = """
        SELECT DISTINCT p.Grupo AS grupo_codigo, sg.Codigo AS codigo, sg.Descricao AS descricao
        FROM produto p
        JOIN SubGrupo sg ON sg.Codigo = p.SubGrupo
        WHERE p.Grupo IS NOT NULL
        ORDER BY p.Grupo, sg.Descricao
    """
    mapa: dict[int, list[dict]] = {}
    for r in executar_query(sql_com_subgrupo):
        mapa.setdefault(int(r["grupo_codigo"]), []).append(
            {"codigo": int(r["codigo"]), "descricao": r["descricao"] or f"Subgrupo {r['codigo']}"}
        )

    sql_sem_subgrupo = """
        SELECT DISTINCT p.Grupo AS grupo_codigo
        FROM produto p
        WHERE p.Grupo IS NOT NULL
          AND (p.SubGrupo IS NULL OR p.SubGrupo NOT IN (SELECT Codigo FROM SubGrupo))
    """
    for r in executar_query(sql_sem_subgrupo):
        grupo = int(r["grupo_codigo"])
        mapa.setdefault(grupo, []).insert(0, {"codigo": SEM_SUBGRUPO_CODIGO, "descricao": SEM_SUBGRUPO_DESCRICAO})
    return mapa


def listar_pdvs_disponiveis() -> list[int]:
    """PDVs distintos com vendas registradas no SQL Server, para a tela de setores."""
    sql = "SELECT DISTINCT PDV FROM Venda WHERE PDV IS NOT NULL ORDER BY PDV"
    rows = executar_query(sql)
    return [int(r["PDV"]) for r in rows]
