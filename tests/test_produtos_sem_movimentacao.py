from datetime import date
from decimal import Decimal

import pytest

from services import dashboard_service as ds
from services import setores_service as ss
from services import vendas_service


@pytest.fixture
def setor(temp_db, monkeypatch):
    setor = ss.criar_setor("Padaria")
    ss.definir_grupos_do_setor(setor["id"], [10])
    monkeypatch.setattr(vendas_service, "listar_grupos_disponiveis", lambda: [{"codigo": 10, "descricao": "PADARIA"}])
    return setor


def _simular(monkeypatch, vendas_por_periodo, cadastro):
    """vendas_por_periodo: {data_ini: [codigos vendidos]}; registra o vendidos_desde pedido."""
    chamadas = {}

    def vendas(_grupos, data_ini, _data_fim, **_kw):
        return {c: {"nome": "", "grupo_codigo": 10, "total": Decimal("1")} for c in vendas_por_periodo.get(data_ini, [])}

    def produtos(_grupos, _subgrupos=None, vendidos_desde=None):
        chamadas["vendidos_desde"] = vendidos_desde
        return [p for p in cadastro if vendidos_desde is None or (p["ultima_venda"] and p["ultima_venda"] >= vendidos_desde)]

    monkeypatch.setattr(vendas_service, "vendas_por_produto", vendas)
    monkeypatch.setattr(vendas_service, "produtos_do_cadastro", produtos)
    return chamadas


def _produto(codigo, ultima_venda):
    return {"codigo": codigo, "nome": f"Produto {codigo}", "grupo_codigo": 10, "ultima_venda": ultima_venda}


def test_lista_so_quem_nao_vendeu_em_nenhum_dos_periodos(setor, monkeypatch):
    cadastro = [_produto(1, date(2026, 3, 2)), _produto(2, date(2026, 3, 9)), _produto(3, date(2025, 3, 5)),
                _produto(4, date(2026, 1, 20))]
    # março/2026 contra março/2025: 1 vendeu no atual, 3 vendeu no comparativo
    chamadas = _simular(monkeypatch, {date(2026, 3, 1): [1], date(2025, 3, 1): [3]}, cadastro)

    resultado = ds.montar_produtos_sem_movimentacao(setor["id"], 2026, 3, "MESMO_MES_ANO_ANTERIOR")

    assert resultado["disponivel"] is True
    assert chamadas["vendidos_desde"] == date(2025, 3, 1)  # janela de 12 meses
    produtos = resultado["grupos"][0]["produtos"]
    assert [p["codigo"] for p in produtos] == [2, 4]  # mais recente primeiro
    assert resultado["total"] == 2
    assert resultado["grupos"][0]["descricao"] == "PADARIA"


def test_incluir_antigos_tira_o_corte_de_12_meses(setor, monkeypatch):
    cadastro = [_produto(1, date(2019, 5, 1)), _produto(2, None)]
    chamadas = _simular(monkeypatch, {}, cadastro)

    resultado = ds.montar_produtos_sem_movimentacao(setor["id"], 2026, 3, "MES_ANTERIOR", incluir_antigos=True)

    assert chamadas["vendidos_desde"] is None
    assert resultado["vendidos_desde"] is None
    assert resultado["total"] == 2


def test_setor_definido_por_pdv_nao_tem_lista(temp_db, monkeypatch):
    delivery = ss.criar_setor("Delivery", pdv_incluidos=[6])
    _simular(monkeypatch, {}, [_produto(1, date(2026, 3, 1))])

    resultado = ds.montar_produtos_sem_movimentacao(delivery["id"], 2026, 3)

    assert resultado["disponivel"] is False
    assert "PDV" in resultado["motivo"]
    assert resultado["grupos"] == []


def test_meses_antes_atravessa_o_ano():
    assert ds._meses_antes(date(2026, 3, 15), 12) == date(2025, 3, 1)
    assert ds._meses_antes(date(2026, 1, 1), 1) == date(2025, 12, 1)
