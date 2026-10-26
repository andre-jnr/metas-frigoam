from datetime import date
from decimal import Decimal

import pytest

from services import calculos
from services import metas_automaticas_service as mas
from services import metas_service as ms
from services import setores_service as ss
from services import vendas_service
from services.errors import ValidationError

HOJE = date(2026, 5, 15)


@pytest.fixture
def setor(temp_db):
    return ss.criar_setor("Açougue")


def _vendas(monkeypatch, por_mes):
    """por_mes(ano, mes) -> venda do mês; conta as consultas feitas."""
    chamadas = []

    def faturamento(_grupos, data_ini, _data_fim, **_kwargs):
        chamadas.append((data_ini.year, data_ini.month))
        return Decimal(str(por_mes(data_ini.year, data_ini.month)))

    monkeypatch.setattr(vendas_service, "faturamento_periodo", faturamento)
    return chamadas


def _percentuais(setor_id):
    return [(m["mes"], m["percentual_meta"]) for m in sorted(ms.listar_metas(setor_id), key=lambda m: m["mes"])]


def test_escada_sobe_e_desce_nos_degraus_certos():
    p, subindo = Decimal("5"), []
    for _ in range(7):
        p = calculos.proximo_percentual(p, True, 3)
        subindo.append(int(p))
    assert subindo == [8, 10, 13, 15, 18, 20, 23]
    descendo = []
    for _ in range(7):
        p = calculos.proximo_percentual(p, False, 3)
        descendo.append(int(p))
    assert descendo == [20, 18, 15, 13, 10, 8, 5]


def test_escada_respeita_minimo_maximo_e_valor_fora_da_escada():
    assert calculos.proximo_percentual(5, False, 5) == 5
    assert calculos.proximo_percentual(20, True, 3, 20) == 20
    assert calculos.proximo_percentual(6, True, 3) == 8
    assert calculos.proximo_percentual(6, False, 3) == 5


def test_setor_que_bate_todo_mes_sobe_a_escada(setor, monkeypatch):
    # vendas crescem 20% ao mês: com base no mês anterior, toda meta até +20% é batida
    _vendas(monkeypatch, lambda ano, mes: 100000 * 1.2 ** (mes + 12 * (ano - 2026)))
    mas.salvar_regra(setor["id"], 2026, 1, 5, "MES_ANTERIOR", hoje=HOJE)
    assert _percentuais(setor["id"]) == [(1, 5), (2, 8), (3, 10), (4, 13), (5, 15)]


def test_setor_que_nao_bate_desce_ate_o_minimo(setor, monkeypatch):
    _vendas(monkeypatch, lambda ano, mes: 100000)
    regra = mas.salvar_regra(setor["id"], 2026, 1, 10, "MES_ANTERIOR", percentual_minimo=5, hoje=HOJE)
    assert _percentuais(setor["id"]) == [(1, 10), (2, 8), (3, 5), (4, 5), (5, 5)]
    resultados = [h["bateu"] for h in regra["historico"]]
    assert resultados == [False, False, False, False, None]  # maio ainda em andamento


def test_metas_geradas_ficam_congeladas(setor, monkeypatch):
    chamadas = _vendas(monkeypatch, lambda ano, mes: 100000)
    mas.salvar_regra(setor["id"], 2026, 1, 5, "MES_ANTERIOR", hoje=HOJE)
    chamadas.clear()
    assert mas.sincronizar_todas(HOJE) == 0
    assert chamadas == []
    assert mas.sincronizar_todas(date(2026, 6, 2)) == 1  # mês novo: só ele é gerado


def test_meta_editada_vira_manual_e_a_escada_continua_dela(setor, monkeypatch):
    _vendas(monkeypatch, lambda ano, mes: 100000 * 1.2 ** mes)
    mas.salvar_regra(setor["id"], 2026, 1, 5, "MES_ANTERIOR", hoje=date(2026, 2, 10))
    fevereiro = next(m for m in ms.listar_metas(setor["id"]) if m["mes"] == 2)
    ms.atualizar_meta(fevereiro["id"], setor["id"], 2026, 2, "PERCENTUAL", 15, None, "MES_ANTERIOR")
    mas.sincronizar_todas(date(2026, 3, 10))
    metas = {m["mes"]: m for m in ms.listar_metas(setor["id"])}
    assert metas[2]["automatica"] is False and metas[2]["percentual_meta"] == 15
    assert metas[3]["automatica"] is True and metas[3]["percentual_meta"] == 18

    # salvar a regra de novo refaz só as automáticas; a manual fica
    mas.salvar_regra(setor["id"], 2026, 1, 5, "MES_ANTERIOR", hoje=date(2026, 3, 10))
    assert _percentuais(setor["id"]) == [(1, 5), (2, 15), (3, 18)]


def test_excluir_regra_mantem_metas_e_para_de_gerar(setor, monkeypatch):
    _vendas(monkeypatch, lambda ano, mes: 100000)
    mas.salvar_regra(setor["id"], 2026, 4, 5, "MESMO_MES_ANO_ANTERIOR", hoje=HOJE)
    mas.excluir_regra(setor["id"])
    assert mas.listar_regras() == []
    assert mas.sincronizar_todas(date(2026, 7, 1)) == 0
    assert len(ms.listar_metas(setor["id"])) == 2


@pytest.mark.parametrize("kwargs", [
    dict(base_comparacao="NAO_APLICAVEL"),
    dict(percentual_inicial=2),  # abaixo do mínimo padrão (3%)
    dict(percentual_maximo=10, percentual_inicial=13),
    dict(mes_inicio=13),
])
def test_regra_invalida(setor, kwargs):
    dados = dict(ano_inicio=2026, mes_inicio=1, percentual_inicial=5, base_comparacao="MES_ANTERIOR")
    dados.update(kwargs)
    with pytest.raises(ValidationError):
        mas.salvar_regra(setor["id"], **dados, hoje=HOJE)
