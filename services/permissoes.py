"""Versões 'só porcentagem' das respostas do dashboard, para usuários sem permissão de ver
valores em R$. Os valores são tirados no servidor (não só escondidos na tela), então não
aparecem nem olhando a resposta da API no navegador.

As funções nunca alteram o dicionário recebido: o dashboard fica em cache e é o mesmo
para todos os usuários."""

from decimal import Decimal

from services import calculos

CAMPOS_MONETARIOS_SETOR = ("meta_final", "venda_realizada", "venda_base", "valor_esperado")
CAMPOS_MONETARIOS_RESUMO = ("faturamento_total", "meta_total")


def _sem_campos(dados: dict, campos) -> dict:
    return {k: (None if k in campos else v) for k, v in dados.items()}


def dashboard_sem_valores(dados: dict) -> dict:
    return {
        **dados,
        "somente_percentual": True,
        "resumo": _sem_campos(dados["resumo"], CAMPOS_MONETARIOS_RESUMO),
        "setores": [_sem_campos(s, CAMPOS_MONETARIOS_SETOR) for s in dados["setores"]],
    }


def _pct(parte: Decimal, total: Decimal) -> str | None:
    if total <= 0:
        return None
    return str((parte / total * Decimal("100")).quantize(calculos.TWOPLACES))


def setor_sem_valores(dados: dict) -> dict:
    """Detalhe do setor em porcentagem:
    - evolução diária: venda e meta acumuladas como % da meta do mês;
    - grupos: participação de cada grupo na venda do setor;
    - comparações: só a variação % contra o mês anterior e o ano anterior."""
    meta_final = Decimal(dados["meta_final"])
    evolucao = [
        {
            "dia": d["dia"],
            "acumulado_pct": _pct(Decimal(d["acumulado"]), meta_final),
            "meta_acumulada_pct": _pct(Decimal(d["meta_acumulada"]), meta_final),
        }
        for d in dados["evolucao_diaria"]
    ]
    total_grupos = sum((Decimal(r["total"]) for r in dados["ranking_grupos"]), Decimal("0"))
    ranking = [
        {k: v for k, v in r.items() if k != "total"} | {"participacao_pct": _pct(Decimal(r["total"]), total_grupos)}
        for r in dados["ranking_grupos"]
    ]
    venda = Decimal(dados["venda_realizada"])
    variacao_mes = calculos.variacao_percentual(venda, Decimal(dados["comparacao"]["venda_mes_anterior"]))
    variacao_ano = calculos.variacao_percentual(venda, Decimal(dados["comparacao"]["venda_mesmo_mes_ano_anterior"]))
    return {
        **_sem_campos(dados, CAMPOS_MONETARIOS_SETOR),
        "somente_percentual": True,
        "evolucao_diaria": evolucao,
        "ranking_grupos": ranking,
        "comparacao": {
            "variacao_mes_anterior_pct": str(variacao_mes) if variacao_mes is not None else None,
            "variacao_mesmo_mes_ano_anterior_pct": str(variacao_ano) if variacao_ano is not None else None,
        },
    }
