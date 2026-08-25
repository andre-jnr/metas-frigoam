"""Testa as funções puras de montagem de filtro (sem I/O) do vendas_service."""

from services import vendas_service as vs


def test_tem_algum_filtro_setor_nao_configurado():
    assert vs._tem_algum_filtro([], None, None, None) is False


def test_tem_algum_filtro_com_grupo():
    assert vs._tem_algum_filtro([1, 2], None, None, None) is True


def test_tem_algum_filtro_com_pdv_incluido_sem_grupo():
    # caso "Delivery": sem grupo, mas com PDV -> considera todos os produtos
    assert vs._tem_algum_filtro([], [6], None, None) is True


def test_tem_algum_filtro_com_dias_excluidos():
    assert vs._tem_algum_filtro([], None, None, [6]) is True


def test_clausula_pdv_dia_vazia():
    sql, params = vs._clausula_pdv_dia(None, None, None)
    assert sql == ""
    assert params == []


def test_clausula_pdv_incluidos():
    sql, params = vs._clausula_pdv_dia([6], None, None)
    assert "v.PDV IN (?)" in sql
    assert params == [6]


def test_clausula_pdv_excluidos():
    sql, params = vs._clausula_pdv_dia(None, [6], None)
    assert "v.PDV NOT IN (?)" in sql
    assert params == [6]


def test_clausula_dias_semana_excluidos_domingo():
    # Domingo = 6 na convenção 0=Segunda...6=Domingo
    sql, params = vs._clausula_pdv_dia(None, None, [6])
    assert "DATEDIFF(day, 0, v.Data) % 7) NOT IN (?)" in sql
    assert params == [6]


def test_clausula_combina_todos_os_filtros():
    sql, params = vs._clausula_pdv_dia([6], [7, 8], [6])
    assert sql.count("AND") == 3
    assert params == [6, 7, 8, 6]


def test_clausula_deduplica_e_ordena():
    sql, params = vs._clausula_pdv_dia([6, 6, 3], None, None)
    assert params == [3, 6]


def test_clausula_grupo_vazia_sem_grupos():
    sql, params = vs._clausula_grupo([], None)
    assert sql == ""
    assert params == []


def test_clausula_grupo_sem_narrowing_inclui_grupo_inteiro():
    sql, params = vs._clausula_grupo([1, 2], None)
    assert sql == " AND (p.Grupo = ? OR p.Grupo = ?)"
    assert params == [1, 2]


def test_clausula_grupo_com_narrowing_restringe_subgrupo():
    sql, params = vs._clausula_grupo([1], {1: [10, 20]})
    assert sql == " AND ((p.Grupo = ? AND (p.SubGrupo IN (?,?))))"
    assert params == [1, 10, 20]


def test_clausula_grupo_mistura_grupo_completo_e_restrito():
    sql, params = vs._clausula_grupo([1, 2], {1: [10, 20]})
    assert sql == " AND ((p.Grupo = ? AND (p.SubGrupo IN (?,?))) OR p.Grupo = ?)"
    assert params == [1, 10, 20, 2]


def test_clausula_grupo_dedup_e_ordena_grupos_e_subgrupos():
    sql, params = vs._clausula_grupo([2, 1, 1], {1: [20, 10, 10]})
    assert sql == " AND ((p.Grupo = ? AND (p.SubGrupo IN (?,?))) OR p.Grupo = ?)"
    assert params == [1, 10, 20, 2]


def test_clausula_grupo_narrowing_so_sem_subgrupo():
    sql, params = vs._clausula_grupo([33], {33: [vs.SEM_SUBGRUPO_CODIGO]})
    assert sql == " AND ((p.Grupo = ? AND (p.SubGrupo IS NULL OR p.SubGrupo NOT IN (SELECT Codigo FROM SubGrupo))))"
    assert params == [33]


def test_clausula_grupo_narrowing_combina_subgrupo_real_e_sem_subgrupo():
    sql, params = vs._clausula_grupo([33], {33: [17, vs.SEM_SUBGRUPO_CODIGO]})
    assert sql == (
        " AND ((p.Grupo = ? AND (p.SubGrupo IN (?) OR p.SubGrupo IS NULL "
        "OR p.SubGrupo NOT IN (SELECT Codigo FROM SubGrupo))))"
    )
    assert params == [33, 17]
