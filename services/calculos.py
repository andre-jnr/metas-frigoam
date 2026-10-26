"""Regras de negócio puras (sem I/O) para cálculo de metas. Seções 53-56 do spec.

Todas as funções financeiras usam Decimal para evitar erro de ponto flutuante.
"""

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

STATUS_META_BATIDA = "META_BATIDA"
STATUS_NO_RITMO = "NO_RITMO"
STATUS_ABAIXO_DO_RITMO = "ABAIXO_DO_RITMO"

TWOPLACES = Decimal("0.01")


def _dec(valor) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def dias_no_mes(ano: int, mes: int) -> int:
    """Quantidade real de dias do mês, considerando ano bissexto."""
    return calendar.monthrange(ano, mes)[1]


def meta_fixa(valor: Decimal | float) -> Decimal:
    return _dec(valor).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def meta_percentual(venda_base: Decimal | float, percentual: Decimal | float) -> Decimal:
    """meta = venda_base * (1 + percentual/100)"""
    venda_base = _dec(venda_base)
    percentual = _dec(percentual)
    fator = Decimal("1") + (percentual / Decimal("100"))
    return (venda_base * fator).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def percentual_realizado(venda: Decimal | float, meta: Decimal | float) -> Decimal:
    """venda / meta * 100. Meta <= 0 é tratada sem ZeroDivisionError."""
    venda = _dec(venda)
    meta = _dec(meta)
    if meta <= 0:
        return Decimal("100.00") if venda > 0 else Decimal("0.00")
    return (venda / meta * Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def percentual_esperado(ano: int, mes: int, referencia: date | None = None) -> Decimal:
    """100% se o mês já encerrou, 0% se o mês ainda não começou,
    ou dia_atual/dias_do_mes*100 (capado em 100) se for o mês corrente."""
    referencia = referencia or date.today()

    if (ano, mes) < (referencia.year, referencia.month):
        return Decimal("100.00")
    if (ano, mes) > (referencia.year, referencia.month):
        return Decimal("0.00")

    total_dias = dias_no_mes(ano, mes)
    dia_atual = referencia.day
    pct = (Decimal(dia_atual) / Decimal(total_dias)) * Decimal("100")
    pct = min(pct, Decimal("100"))
    return pct.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def valor_esperado(meta_final: Decimal | float, pct_esperado: Decimal | float) -> Decimal:
    meta_final = _dec(meta_final)
    pct_esperado = _dec(pct_esperado)
    return (meta_final * pct_esperado / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def diferenca(pct_realizado: Decimal | float, pct_esperado: Decimal | float) -> Decimal:
    """Diferença em pontos percentuais (realizado - esperado)."""
    return (_dec(pct_realizado) - _dec(pct_esperado)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def status_setor(pct_realizado: Decimal | float, pct_esperado: Decimal | float) -> str:
    pct_realizado = _dec(pct_realizado)
    pct_esperado = _dec(pct_esperado)
    if pct_realizado >= Decimal("100"):
        return STATUS_META_BATIDA
    if pct_realizado >= pct_esperado:
        return STATUS_NO_RITMO
    return STATUS_ABAIXO_DO_RITMO


def possui_estrela(status: str) -> bool:
    return status in (STATUS_META_BATIDA, STATUS_NO_RITMO)


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    if mes == 1:
        return ano - 1, 12
    return ano, mes - 1


def mesmo_mes_ano_anterior(ano: int, mes: int) -> tuple[int, int]:
    return ano - 1, mes


def periodo_do_mes(ano: int, mes: int) -> tuple[date, date]:
    """Primeiro e último dia do mês (calendário real)."""
    return date(ano, mes, 1), date(ano, mes, dias_no_mes(ano, mes))


def dia_referencia_periodo(ano: int, mes: int, referencia: date | None = None) -> int:
    """Quantos dias do mês entram na análise de 'período equivalente' (usada pela
    tabela de detalhamento por produto — NÃO usada pelo cálculo de metas nem
    pelos cards de Comparações, que continuam comparando o mês cheio anterior).

    Mês já encerrado -> mês cheio. Mês corrente -> até o dia de hoje. Mês
    futuro -> 1 (intervalo mínimo, sem dado relevante esperado)."""
    referencia = referencia or date.today()
    if (ano, mes) < (referencia.year, referencia.month):
        return dias_no_mes(ano, mes)
    if (ano, mes) > (referencia.year, referencia.month):
        return 1
    return min(referencia.day, dias_no_mes(ano, mes))


def periodo_equivalente(ano: int, mes: int, referencia: date | None = None) -> tuple[date, date]:
    """Do dia 1 até dia_referencia_periodo do mês informado."""
    dia = dia_referencia_periodo(ano, mes, referencia)
    return date(ano, mes, 1), date(ano, mes, dia)


def periodo_equivalente_base(ano_base: int, mes_base: int, dias: int) -> tuple[date, date]:
    """Mesmo intervalo de dias do período atual, aplicado ao mês-base — capado
    ao tamanho real do mês-base (ex: comparar 29 dias de fevereiro bissexto
    contra um fevereiro de 28 dias)."""
    dia_fim = min(dias, dias_no_mes(ano_base, mes_base))
    return date(ano_base, mes_base, 1), date(ano_base, mes_base, dia_fim)


def variacao_percentual(atual: Decimal | float, comparativo: Decimal | float) -> Decimal | None:
    """(atual - comparativo) / comparativo * 100. None quando comparativo <= 0
    (divisão por zero) — o chamador deve exibir algo como '—' nesse caso."""
    atual = _dec(atual)
    comparativo = _dec(comparativo)
    if comparativo <= 0:
        return None
    return ((atual - comparativo) / comparativo * Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


# ---------- Escada das metas automáticas ----------
# Degraus de 2,5 em 2,5 pontos arredondados: 0, 3, 5, 8, 10, 13, 15, 18, 20, 23, 25...
PASSO_ESCADA = Decimal("2.5")


def degrau_escada(indice: int) -> Decimal:
    return (PASSO_ESCADA * indice).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def proximo_percentual(
    atual: Decimal | float, bateu: bool, minimo: Decimal | float, maximo: Decimal | float | None = None
) -> Decimal:
    """Bateu a meta do mês anterior -> sobe para o próximo degrau acima de `atual`;
    não bateu -> desce para o degrau abaixo. O resultado fica entre `minimo` e `maximo`
    (sem teto quando maximo é None). Funciona também com `atual` fora da escada (ex.: 6%)."""
    atual = _dec(atual)
    minimo = _dec(minimo)
    indice = 0
    while degrau_escada(indice) <= atual:
        indice += 1
    # aqui degrau_escada(indice) é o primeiro degrau acima de `atual`
    if bateu:
        novo = degrau_escada(indice)
    else:
        indice -= 1
        if degrau_escada(indice) == atual:
            indice -= 1
        novo = degrau_escada(max(indice, 0))
    if maximo is not None:
        novo = min(novo, _dec(maximo))
    return max(novo, minimo)
