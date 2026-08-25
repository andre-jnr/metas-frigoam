from decimal import Decimal

import pytest

from services import metas_service as ms
from services import setores_service as ss
from services import vendas_service
from services.errors import ValidationError


@pytest.fixture
def setor(temp_db):
    s = ss.criar_setor("Açougue")
    ss.definir_grupos_do_setor(s["id"], [1, 2])
    return s


def test_criar_meta_valor_fixo(temp_db, setor):
    meta = ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=500000)
    assert meta["tipo_meta"] == "VALOR_FIXO"
    assert meta["valor_meta"] == 500000.0
    assert meta["base_comparacao"] == "NAO_APLICAVEL"


def test_criar_meta_valor_fixo_invalido(temp_db, setor):
    with pytest.raises(ValidationError):
        ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=0)


def test_criar_meta_percentual_com_historico(temp_db, setor, monkeypatch):
    # venda base (mesmo mês ano anterior) = 400.000; +10% -> 440.000 (exemplo da seção 10)
    monkeypatch.setattr(vendas_service, "faturamento_periodo", lambda *a, **k: Decimal("400000"))
    meta = ms.criar_meta(
        setor["id"], 2026, 8, "PERCENTUAL",
        percentual_meta=10, base_comparacao="MESMO_MES_ANO_ANTERIOR",
    )
    listadas = ms.listar_metas(setor_id=setor["id"])
    assert listadas[0]["valor_calculado"] == "440000.00"
    assert listadas[0]["venda_base"] == "400000"


def test_criar_meta_percentual_sem_historico_bloqueia_sem_confirmacao(temp_db, setor, monkeypatch):
    monkeypatch.setattr(vendas_service, "faturamento_periodo", lambda *a, **k: Decimal("0"))
    with pytest.raises(ValidationError) as exc_info:
        ms.criar_meta(setor["id"], 2026, 8, "PERCENTUAL", percentual_meta=10, base_comparacao="MES_ANTERIOR")
    assert exc_info.value.status_code == 422


def test_criar_meta_percentual_sem_historico_com_confirmacao(temp_db, setor, monkeypatch):
    monkeypatch.setattr(vendas_service, "faturamento_periodo", lambda *a, **k: Decimal("0"))
    meta = ms.criar_meta(
        setor["id"], 2026, 8, "PERCENTUAL",
        percentual_meta=10, base_comparacao="MES_ANTERIOR", confirmar_zero=True,
    )
    listadas = ms.listar_metas(setor_id=setor["id"])
    assert listadas[0]["valor_calculado"] == "0.00"


def test_meta_duplicada_mesmo_setor_periodo(temp_db, setor):
    ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=100000)
    with pytest.raises(ValidationError):
        ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=200000)


def test_setor_inexistente(temp_db):
    with pytest.raises(ValidationError):
        ms.criar_meta(9999, 2026, 8, "VALOR_FIXO", valor_meta=100000)


def test_excluir_meta_inexistente(temp_db):
    with pytest.raises(ValidationError):
        ms.excluir_meta(9999)


def test_meta_ativa_do_setor(temp_db, setor):
    ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=100000)
    ativa = ms.meta_ativa_do_setor(setor["id"], 2026, 8)
    assert ativa is not None
    assert ativa["valor_meta"] == 100000.0
    assert ms.meta_ativa_do_setor(setor["id"], 2026, 7) is None


def test_metas_ativas_por_setores(temp_db, setor, monkeypatch):
    outro_setor = ss.criar_setor("Bebidas")
    ms.criar_meta(setor["id"], 2026, 8, "VALOR_FIXO", valor_meta=100000)
    mapa = ms.metas_ativas_por_setores([setor["id"], outro_setor["id"]], 2026, 8)
    assert setor["id"] in mapa
    assert outro_setor["id"] not in mapa
