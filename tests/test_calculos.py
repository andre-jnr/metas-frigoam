from datetime import date
from decimal import Decimal

from services import calculos as c


def test_dias_no_mes_normal():
    assert c.dias_no_mes(2026, 1) == 31
    assert c.dias_no_mes(2026, 4) == 30


def test_dias_no_mes_fevereiro_bissexto():
    assert c.dias_no_mes(2024, 2) == 29  # 2024 é bissexto
    assert c.dias_no_mes(2025, 2) == 28  # 2025 não é


def test_meta_fixa():
    assert c.meta_fixa(500000) == Decimal("500000.00")
    assert c.meta_fixa("500000.5") == Decimal("500000.50")


def test_meta_percentual_mesmo_mes_ano_anterior():
    # 400.000 x 1.10 = 440.000 (exemplo da seção 10)
    assert c.meta_percentual(Decimal("400000"), Decimal("10")) == Decimal("440000.00")


def test_meta_percentual_negativa():
    assert c.meta_percentual(Decimal("100000"), Decimal("-10")) == Decimal("90000.00")


def test_percentual_realizado_venda_acima_da_meta():
    assert c.percentual_realizado(Decimal("625000"), Decimal("500000")) == Decimal("125.00")


def test_percentual_realizado_venda_abaixo_da_meta():
    assert c.percentual_realizado(Decimal("250000"), Decimal("500000")) == Decimal("50.00")


def test_percentual_realizado_meta_zero_sem_venda():
    assert c.percentual_realizado(Decimal("0"), Decimal("0")) == Decimal("0.00")


def test_percentual_realizado_meta_zero_com_venda():
    assert c.percentual_realizado(Decimal("100"), Decimal("0")) == Decimal("100.00")


def test_percentual_esperado_mes_encerrado():
    # Estamos "hoje" em agosto/2026; julho/2026 já encerrou -> 100%
    referencia = date(2026, 8, 5)
    assert c.percentual_esperado(2026, 7, referencia) == Decimal("100.00")


def test_percentual_esperado_mes_futuro():
    referencia = date(2026, 8, 5)
    assert c.percentual_esperado(2026, 9, referencia) == Decimal("0.00")


def test_percentual_esperado_mes_corrente_exemplo_spec():
    # Agosto tem 31 dias, hoje é dia 5 -> 5/31*100 = 16.13%
    referencia = date(2026, 8, 5)
    assert c.percentual_esperado(2026, 8, referencia) == Decimal("16.13")


def test_percentual_esperado_primeiro_dia_do_mes():
    referencia = date(2026, 8, 1)
    esperado = (Decimal(1) / Decimal(31) * 100).quantize(Decimal("0.01"))
    assert c.percentual_esperado(2026, 8, referencia) == esperado


def test_percentual_esperado_ultimo_dia_do_mes():
    referencia = date(2026, 8, 31)
    assert c.percentual_esperado(2026, 8, referencia) == Decimal("100.00")


def test_valor_esperado():
    # Meta 310.000, esperado 16.13% -> 50.003,00 (aprox)
    resultado = c.valor_esperado(Decimal("310000"), Decimal("16.13"))
    assert resultado == Decimal("50003.00")


def test_diferenca_positiva_e_negativa():
    assert c.diferenca(Decimal("57.4"), Decimal("52.3")) == Decimal("5.10")
    assert c.diferenca(Decimal("40"), Decimal("50")) == Decimal("-10.00")


def test_status_meta_batida():
    assert c.status_setor(Decimal("103.2"), Decimal("52.3")) == c.STATUS_META_BATIDA


def test_status_no_ritmo():
    assert c.status_setor(Decimal("60"), Decimal("50")) == c.STATUS_NO_RITMO


def test_status_abaixo_do_ritmo():
    assert c.status_setor(Decimal("46.8"), Decimal("50")) == c.STATUS_ABAIXO_DO_RITMO


def test_setor_sem_vendas():
    pct = c.percentual_realizado(Decimal("0"), Decimal("500000"))
    assert pct == Decimal("0.00")
    assert c.status_setor(pct, Decimal("50")) == c.STATUS_ABAIXO_DO_RITMO


def test_possui_estrela():
    assert c.possui_estrela(c.STATUS_META_BATIDA) is True
    assert c.possui_estrela(c.STATUS_NO_RITMO) is True
    assert c.possui_estrela(c.STATUS_ABAIXO_DO_RITMO) is False


def test_mes_anterior_dentro_do_ano():
    assert c.mes_anterior(2026, 8) == (2026, 7)


def test_mes_anterior_virada_de_ano():
    assert c.mes_anterior(2026, 1) == (2025, 12)


def test_mesmo_mes_ano_anterior():
    assert c.mesmo_mes_ano_anterior(2026, 8) == (2025, 8)


def test_periodo_do_mes():
    assert c.periodo_do_mes(2026, 8) == (date(2026, 8, 1), date(2026, 8, 31))
    assert c.periodo_do_mes(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))


# ===== Período equivalente (tabela de detalhamento por produto) =====

def test_periodo_equivalente_dia_6_exemplo_do_pedido():
    referencia = date(2026, 8, 6)
    assert c.periodo_equivalente(2026, 8, referencia) == (date(2026, 8, 1), date(2026, 8, 6))


def test_periodo_equivalente_base_ano_anterior_dia_6():
    # mesmo mês do ano anterior, mesmo intervalo de dias (1-6)
    assert c.periodo_equivalente_base(2025, 8, 6) == (date(2025, 8, 1), date(2025, 8, 6))


def test_periodo_equivalente_base_mes_anterior_dia_6():
    assert c.periodo_equivalente_base(2026, 7, 6) == (date(2026, 7, 1), date(2026, 7, 6))


def test_periodo_equivalente_dia_15():
    referencia = date(2026, 8, 15)
    assert c.periodo_equivalente(2026, 8, referencia) == (date(2026, 8, 1), date(2026, 8, 15))
    assert c.periodo_equivalente_base(2025, 8, 15) == (date(2025, 8, 1), date(2025, 8, 15))
    assert c.periodo_equivalente_base(2026, 7, 15) == (date(2026, 7, 1), date(2026, 7, 15))


def test_periodo_equivalente_dia_20_muda_dinamicamente():
    referencia = date(2026, 8, 20)
    assert c.periodo_equivalente(2026, 8, referencia) == (date(2026, 8, 1), date(2026, 8, 20))
    assert c.periodo_equivalente_base(2025, 8, 20) == (date(2025, 8, 1), date(2025, 8, 20))
    assert c.periodo_equivalente_base(2026, 7, 20) == (date(2026, 7, 1), date(2026, 7, 20))


def test_periodo_equivalente_mes_encerrado_usa_mes_cheio():
    # visualizando julho/2026 enquanto "hoje" já é agosto/2026: mês fechado -> completo
    referencia = date(2026, 8, 6)
    assert c.periodo_equivalente(2026, 7, referencia) == (date(2026, 7, 1), date(2026, 7, 31))


def test_periodo_equivalente_mes_futuro():
    referencia = date(2026, 8, 6)
    ini, fim = c.periodo_equivalente(2026, 9, referencia)
    assert ini == date(2026, 9, 1)
    assert fim == date(2026, 9, 1)  # intervalo mínimo, sem crash


def test_periodo_equivalente_base_capa_mes_mais_curto():
    # período atual foi até o dia 29 (fevereiro bissexto); base é fevereiro não-bissexto (28 dias)
    assert c.periodo_equivalente_base(2025, 2, 29) == (date(2025, 2, 1), date(2025, 2, 28))


def test_variacao_percentual_crescimento():
    assert c.variacao_percentual(Decimal("12000"), Decimal("10000")) == Decimal("20.00")


def test_variacao_percentual_queda():
    assert c.variacao_percentual(Decimal("7000"), Decimal("8000")) == Decimal("-12.50")


def test_variacao_percentual_comparativo_zero_retorna_none():
    assert c.variacao_percentual(Decimal("500"), Decimal("0")) is None
