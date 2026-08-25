import pytest

from services import filiais_service as fs
from services import setores_service as ss
from services.errors import ValidationError


def test_criar_setor_e_listar(temp_db):
    setor = ss.criar_setor("Açougue", "Carnes em geral", 1)
    assert setor["nome"] == "Açougue"
    assert setor["grupos_count"] == 0
    assert len(ss.listar_setores()) == 1


def test_nome_duplicado_gera_validation_error(temp_db):
    ss.criar_setor("Frios")
    with pytest.raises(ValidationError):
        ss.criar_setor("Frios")


def test_nome_vazio_gera_validation_error(temp_db):
    with pytest.raises(ValidationError):
        ss.criar_setor("   ")


def test_grupo_pertencendo_a_multiplos_setores(temp_db):
    setor_a = ss.criar_setor("Açougue")
    setor_b = ss.criar_setor("Bebidas")
    ss.definir_grupos_do_setor(setor_a["id"], [1, 2])
    ss.definir_grupos_do_setor(setor_b["id"], [1, 3])  # grupo 1 associado aos dois setores

    grupos_a = ss.obter_grupos_do_setor(setor_a["id"])
    grupos_b = ss.obter_grupos_do_setor(setor_b["id"])
    assert grupos_a == [1, 2]
    assert grupos_b == [1, 3]


def test_setor_com_multiplos_grupos_sem_duplicidade(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [3, 1, 2, 2, 1])  # entrada com duplicatas
    assert ss.obter_grupos_do_setor(setor["id"]) == [1, 2, 3]
    assert ss.obter_setor(setor["id"])["grupos_count"] == 3


def test_definir_grupos_substitui_associacao_anterior(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1, 2])
    ss.definir_grupos_do_setor(setor["id"], [5])
    assert ss.obter_grupos_do_setor(setor["id"]) == [5]


def test_excluir_setor_remove_associacoes_em_cascata(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1, 2])
    ss.excluir_setor(setor["id"])
    assert ss.obter_setor(setor["id"]) is None
    assert ss.obter_grupos_por_setores([setor["id"]]) == {setor["id"]: []}


def test_alternar_ativo(temp_db):
    setor = ss.criar_setor("Açougue")
    assert setor["ativo"] is True
    desativado = ss.alternar_ativo(setor["id"], False)
    assert desativado["ativo"] is False
    assert ss.listar_setores(apenas_ativos=True) == []


def test_obter_grupos_por_setores_multiplos(temp_db):
    setor_a = ss.criar_setor("Açougue")
    setor_b = ss.criar_setor("Bebidas")
    ss.definir_grupos_do_setor(setor_a["id"], [1])
    mapa = ss.obter_grupos_por_setores([setor_a["id"], setor_b["id"]])
    assert mapa[setor_a["id"]] == [1]
    assert mapa[setor_b["id"]] == []


def test_setor_delivery_por_pdv_sem_grupo(temp_db):
    # "Delivery": todas as vendas do PDV 6, exceto domingo (6 na convenção 0=Segunda..6=Domingo)
    setor = ss.criar_setor("Delivery", pdv_incluidos=[6], dias_semana_excluidos=[6])
    assert setor["grupos_count"] == 0
    assert setor["pdv_incluidos"] == [6]
    assert setor["dias_semana_excluidos"] == [6]
    assert setor["tem_filtro_pdv"] is True


def test_setor_sem_subgrupo_narrowing_por_padrao(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1])
    assert ss.obter_subgrupos_do_setor(setor["id"]) == {}
    assert ss.obter_setor(setor["id"])["tem_filtro_subgrupo"] is False


def test_definir_subgrupos_do_setor_grava_narrowing(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1, 2])
    ss.definir_subgrupos_do_setor(setor["id"], {1: [10, 20]})
    assert ss.obter_subgrupos_do_setor(setor["id"]) == {1: [10, 20]}
    assert ss.obter_setor(setor["id"])["tem_filtro_subgrupo"] is True


def test_definir_subgrupos_substitui_associacao_anterior(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1])
    ss.definir_subgrupos_do_setor(setor["id"], {1: [10, 20]})
    ss.definir_subgrupos_do_setor(setor["id"], {1: [30]})
    assert ss.obter_subgrupos_do_setor(setor["id"]) == {1: [30]}


def test_definir_subgrupos_descarta_grupo_nao_selecionado(temp_db):
    # Usuário desmarcou o grupo 2 por completo; narrowing órfão dele não deve ser gravado.
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1])
    ss.definir_subgrupos_do_setor(setor["id"], {1: [10], 2: [99]}, grupo_codigos_validos=[1])
    assert ss.obter_subgrupos_do_setor(setor["id"]) == {1: [10]}


def test_excluir_setor_remove_subgrupos_em_cascata(temp_db):
    setor = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(setor["id"], [1])
    ss.definir_subgrupos_do_setor(setor["id"], {1: [10, 20]})
    ss.excluir_setor(setor["id"])
    assert ss.obter_subgrupos_por_setores([setor["id"]]) == {setor["id"]: {}}


def test_obter_subgrupos_por_setores_multiplos(temp_db):
    setor_a = ss.criar_setor("Açougue")
    setor_b = ss.criar_setor("Bebidas")
    ss.definir_grupos_do_setor(setor_a["id"], [1])
    ss.definir_subgrupos_do_setor(setor_a["id"], {1: [10]})
    mapa = ss.obter_subgrupos_por_setores([setor_a["id"], setor_b["id"]])
    assert mapa[setor_a["id"]] == {1: [10]}
    assert mapa[setor_b["id"]] == {}


def test_setor_criado_na_filial_ativa(temp_db):
    fs.definir_filial_ativa("prq10")
    setor = ss.criar_setor("Açougue")
    assert setor["id"] is not None
    fs.definir_filial_ativa("pn")
    assert ss.listar_setores() == []


def test_setor_de_outra_filial_fica_invisivel(temp_db):
    setor_pn = ss.criar_setor("Açougue")
    fs.definir_filial_ativa("prq10")
    assert ss.listar_setores() == []
    assert ss.obter_setor(setor_pn["id"]) is None


def test_mesmo_nome_permitido_em_filiais_diferentes(temp_db):
    ss.criar_setor("Açougue")
    fs.definir_filial_ativa("prq10")
    setor_prq10 = ss.criar_setor("Açougue")  # mesmo nome, filial diferente: não deve colidir
    assert setor_prq10["nome"] == "Açougue"
    assert len(ss.listar_setores()) == 1


def test_editar_excluir_setor_de_outra_filial_falha(temp_db):
    setor_pn = ss.criar_setor("Açougue")
    fs.definir_filial_ativa("prq10")
    with pytest.raises(ValidationError):
        ss.atualizar_setor(setor_pn["id"], "Novo nome")
    with pytest.raises(ValidationError):
        ss.excluir_setor(setor_pn["id"])
    fs.definir_filial_ativa("pn")
    assert ss.obter_setor(setor_pn["id"])["nome"] == "Açougue"


def test_setor_loja_exclui_pdv_delivery(temp_db):
    setor = ss.criar_setor("Loja", pdv_excluidos=[6])
    assert setor["pdv_excluidos"] == [6]
    assert setor["tem_filtro_pdv"] is True


def test_setor_sem_filtro_pdv(temp_db):
    setor = ss.criar_setor("Açougue")
    assert setor["pdv_incluidos"] == []
    assert setor["pdv_excluidos"] == []
    assert setor["dias_semana_excluidos"] == []
    assert setor["tem_filtro_pdv"] is False


def test_pdv_invalido_gera_validation_error(temp_db):
    with pytest.raises(ValidationError):
        ss.criar_setor("Delivery", pdv_incluidos=[-1])


def test_dia_semana_invalido_gera_validation_error(temp_db):
    with pytest.raises(ValidationError):
        ss.criar_setor("Delivery", dias_semana_excluidos=[7])


def test_pdv_incluido_e_excluido_ao_mesmo_tempo_gera_erro(temp_db):
    with pytest.raises(ValidationError):
        ss.criar_setor("Delivery", pdv_incluidos=[6], pdv_excluidos=[6])


def test_atualizar_setor_altera_filtro_pdv(temp_db):
    setor = ss.criar_setor("Delivery", pdv_incluidos=[6])
    atualizado = ss.atualizar_setor(setor["id"], "Delivery", pdv_incluidos=[6, 7])
    assert atualizado["pdv_incluidos"] == [6, 7]
