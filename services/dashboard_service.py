"""Orquestra setores + metas + vendas para montar o dashboard, com cache em memória.

Decisão de performance: para a tela principal (N setores de uma vez), fazemos
NO MÁXIMO 1 query de faturamento por período necessário (período atual + até
2 períodos-base distintos para metas percentuais) — nunca uma query por setor.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal

from config import Config
from services import calculos, metas_service, setores_service, vendas_service
from services.errors import ValidationError

logger = logging.getLogger("dashboard_metas.dashboard_service")

_cache: dict[tuple[int, int], dict] = {}


def _periodo_base(ano: int, mes: int, base_comparacao: str):
    if base_comparacao == "MES_ANTERIOR":
        return calculos.periodo_do_mes(*calculos.mes_anterior(ano, mes))
    if base_comparacao == "MESMO_MES_ANO_ANTERIOR":
        return calculos.periodo_do_mes(*calculos.mesmo_mes_ano_anterior(ano, mes))
    return None


def _montar_dashboard(ano: int, mes: int) -> dict:
    setores = setores_service.listar_setores(apenas_ativos=True)
    agora = datetime.now().isoformat(timespec="seconds")

    if not setores:
        return {
            "resumo": {
                "faturamento_total": "0", "meta_total": "0", "percentual_total": "0.00",
                "setores_no_ritmo": 0, "setores_abaixo": 0, "metas_batidas": 0, "total_setores": 0,
            },
            "setores": [], "ano": ano, "mes": mes, "atualizado_em": agora,
        }

    setor_ids = [s["id"] for s in setores]
    grupos_por_setor = setores_service.obter_grupos_por_setores(setor_ids)
    subgrupos_por_setor = setores_service.obter_subgrupos_por_setores(setor_ids)
    metas_por_setor = metas_service.metas_ativas_por_setores(setor_ids, ano, mes)

    data_ini, data_fim = calculos.periodo_do_mes(ano, mes)

    # Setores "simples" (sem filtro de PDV/dia da semana nem narrowing de
    # subgrupo) compartilham UMA query agregada por grupo. Setores "especiais"
    # (ex: Delivery, ou setor com subgrupo restrito) precisam de query própria,
    # pois seu filtro não pode ser resolvido a partir do mapa por grupo.
    setores_simples = [s for s in setores if not s["tem_filtro_pdv"] and not s["tem_filtro_subgrupo"]]
    setores_especiais = [s for s in setores if s["tem_filtro_pdv"] or s["tem_filtro_subgrupo"]]

    mapa_atual = vendas_service.faturamento_por_grupo(data_ini, data_fim) if setores_simples else {}

    periodos_base_necessarios = set()
    for setor in setores_simples:
        meta = metas_por_setor.get(setor["id"])
        if meta and meta["tipo_meta"] == "PERCENTUAL":
            periodo = _periodo_base(ano, mes, meta["base_comparacao"])
            if periodo:
                periodos_base_necessarios.add(periodo)

    mapas_base = {periodo: vendas_service.faturamento_por_grupo(*periodo) for periodo in periodos_base_necessarios}

    pct_esperado = calculos.percentual_esperado(ano, mes)  # igual para todos os setores no mesmo período

    resultado_setores = []
    for setor in setores:
        grupo_codigos = grupos_por_setor.get(setor["id"], [])
        subgrupos_por_grupo = subgrupos_por_setor.get(setor["id"], {})
        especial = setor["tem_filtro_pdv"] or setor["tem_filtro_subgrupo"]
        filtros_pdv = dict(
            pdv_incluidos=setor["pdv_incluidos"], pdv_excluidos=setor["pdv_excluidos"],
            dias_semana_excluidos=setor["dias_semana_excluidos"],
        )

        if especial:
            venda_realizada = vendas_service.faturamento_periodo(
                grupo_codigos, data_ini, data_fim, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
            )
        else:
            venda_realizada = vendas_service.somar_grupos(mapa_atual, grupo_codigos)

        meta = metas_por_setor.get(setor["id"])

        venda_base = None
        if meta is None:
            tem_meta = False
            meta_final = Decimal("0")
        else:
            tem_meta = True
            if meta["tipo_meta"] == "VALOR_FIXO":
                meta_final = calculos.meta_fixa(meta["valor_meta"] or 0)
            else:
                periodo = _periodo_base(ano, mes, meta["base_comparacao"])
                if especial:
                    venda_base = vendas_service.faturamento_periodo(
                        grupo_codigos, *periodo, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
                    )
                else:
                    mapa_base = mapas_base.get(periodo, {})
                    venda_base = vendas_service.somar_grupos(mapa_base, grupo_codigos)
                meta_final = calculos.meta_percentual(venda_base, meta["percentual_meta"] or 0)

        pct_realizado = calculos.percentual_realizado(venda_realizada, meta_final)
        val_esperado = calculos.valor_esperado(meta_final, pct_esperado)
        dif = calculos.diferenca(pct_realizado, pct_esperado)
        status = calculos.status_setor(pct_realizado, pct_esperado) if tem_meta else calculos.STATUS_ABAIXO_DO_RITMO
        estrela = tem_meta and calculos.possui_estrela(status)

        resultado_setores.append({
            "id": setor["id"],
            "nome": setor["nome"],
            "ordem_exibicao": setor["ordem_exibicao"],
            "tem_meta": tem_meta,
            "meta_final": str(meta_final),
            "venda_realizada": str(venda_realizada),
            "venda_base": str(venda_base) if venda_base is not None else None,
            "percentual_realizado": str(pct_realizado),
            "percentual_esperado": str(pct_esperado),
            "valor_esperado": str(val_esperado),
            "diferenca": str(dif),
            "status": status,
            "estrela": estrela,
        })

    resultado_setores.sort(key=lambda s: s["ordem_exibicao"])

    faturamento_total = sum((Decimal(s["venda_realizada"]) for s in resultado_setores), Decimal("0"))
    meta_total = sum((Decimal(s["meta_final"]) for s in resultado_setores), Decimal("0"))
    pct_total = calculos.percentual_realizado(faturamento_total, meta_total)
    no_ritmo = sum(1 for s in resultado_setores if s["status"] == calculos.STATUS_NO_RITMO)
    abaixo = sum(1 for s in resultado_setores if s["status"] == calculos.STATUS_ABAIXO_DO_RITMO)
    batidas = sum(1 for s in resultado_setores if s["status"] == calculos.STATUS_META_BATIDA)

    return {
        "resumo": {
            "faturamento_total": str(faturamento_total),
            "meta_total": str(meta_total),
            "percentual_total": str(pct_total),
            "setores_no_ritmo": no_ritmo,
            "setores_abaixo": abaixo,
            "metas_batidas": batidas,
            "total_setores": len(resultado_setores),
        },
        "setores": resultado_setores,
        "ano": ano,
        "mes": mes,
        "atualizado_em": agora,
    }


def montar_dashboard(ano: int, mes: int, force_refresh: bool = False) -> dict:
    chave = (ano, mes)
    agora = time.time()
    if not force_refresh:
        entrada = _cache.get(chave)
        if entrada and entrada["expira_em"] > agora:
            return entrada["data"]

    dados = _montar_dashboard(ano, mes)
    _cache[chave] = {"data": dados, "expira_em": agora + Config.CACHE_TTL_SECONDS}
    return dados


def invalidar_cache(ano: int | None = None, mes: int | None = None) -> None:
    if ano is None or mes is None:
        _cache.clear()
    else:
        _cache.pop((ano, mes), None)


def montar_dashboard_setor(setor_id: int, ano: int, mes: int) -> dict:
    setor = setores_service.obter_setor(setor_id)
    if setor is None:
        raise ValidationError("Setor não encontrado.", status_code=404)

    grupo_codigos = setores_service.obter_grupos_do_setor(setor_id)
    subgrupos_por_grupo = setores_service.obter_subgrupos_do_setor(setor_id)
    data_ini, data_fim = calculos.periodo_do_mes(ano, mes)
    filtros_pdv = dict(
        pdv_incluidos=setor["pdv_incluidos"], pdv_excluidos=setor["pdv_excluidos"],
        dias_semana_excluidos=setor["dias_semana_excluidos"],
    )

    venda_realizada = vendas_service.faturamento_periodo(
        grupo_codigos, data_ini, data_fim, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    meta = metas_service.meta_ativa_do_setor(setor_id, ano, mes)

    venda_base = None
    if meta is None:
        tem_meta = False
        meta_final = Decimal("0")
    else:
        tem_meta = True
        calc = metas_service.calcular_meta(
            setor_id, ano, mes, meta["tipo_meta"], meta["percentual_meta"], meta["valor_meta"], meta["base_comparacao"]
        )
        meta_final = calc["valor_meta"]
        venda_base = calc["venda_base"]

    pct_realizado = calculos.percentual_realizado(venda_realizada, meta_final)
    pct_esperado = calculos.percentual_esperado(ano, mes)
    val_esperado = calculos.valor_esperado(meta_final, pct_esperado)
    dif = calculos.diferenca(pct_realizado, pct_esperado)
    status = calculos.status_setor(pct_realizado, pct_esperado) if tem_meta else calculos.STATUS_ABAIXO_DO_RITMO

    dias_total = calculos.dias_no_mes(ano, mes)
    meta_diaria = (meta_final / Decimal(dias_total)) if meta_final > 0 else Decimal("0")
    evolucao = vendas_service.evolucao_diaria(
        grupo_codigos, data_ini, data_fim, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    for indice, dia in enumerate(evolucao, start=1):
        dia["meta_acumulada"] = str((meta_diaria * indice).quantize(Decimal("0.01")))
        dia["valor"] = str(dia["valor"])
        dia["acumulado"] = str(dia["acumulado"])

    ranking = vendas_service.ranking_grupos(
        grupo_codigos, data_ini, data_fim, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    for item in ranking:
        item["total"] = str(item["total"])

    periodo_mes_anterior = calculos.periodo_do_mes(*calculos.mes_anterior(ano, mes))
    periodo_ano_anterior = calculos.periodo_do_mes(*calculos.mesmo_mes_ano_anterior(ano, mes))
    venda_mes_anterior = vendas_service.faturamento_periodo(
        grupo_codigos, *periodo_mes_anterior, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    venda_ano_anterior = vendas_service.faturamento_periodo(
        grupo_codigos, *periodo_ano_anterior, subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )

    return {
        "setor": {"id": setor["id"], "nome": setor["nome"], "descricao": setor["descricao"]},
        "ano": ano,
        "mes": mes,
        "tem_meta": tem_meta,
        "meta_final": str(meta_final),
        "venda_realizada": str(venda_realizada),
        "venda_base": str(venda_base) if venda_base is not None else None,
        "percentual_realizado": str(pct_realizado),
        "percentual_esperado": str(pct_esperado),
        "valor_esperado": str(val_esperado),
        "diferenca": str(dif),
        "status": status,
        "estrela": tem_meta and calculos.possui_estrela(status),
        "evolucao_diaria": evolucao,
        "ranking_grupos": ranking,
        "comparacao": {
            "venda_mes_anterior": str(venda_mes_anterior),
            "venda_mesmo_mes_ano_anterior": str(venda_ano_anterior),
        },
    }


TIPOS_COMPARACAO_PRODUTO = ("MESMO_MES_ANO_ANTERIOR", "MES_ANTERIOR")


def montar_produtos_setor(
    setor_id: int, ano: int, mes: int, tipo_comparacao: str | None = None, metrica: str = "valor"
) -> dict:
    """Detalhamento de vendas e metas por produto (drill-down), com período
    'equivalente' (mesmo intervalo de dias em ambos os períodos) — regra
    própria desta tabela, independente da usada no cálculo de metas.
    metrica: "valor" (R$, padrão) ou "quantidade" (unidades/kg vendidos)."""
    if metrica not in vendas_service.METRICAS_PRODUTO:
        metrica = "valor"

    setor = setores_service.obter_setor(setor_id)
    if setor is None:
        raise ValidationError("Setor não encontrado.", status_code=404)

    if tipo_comparacao not in TIPOS_COMPARACAO_PRODUTO:
        meta = metas_service.meta_ativa_do_setor(setor_id, ano, mes)
        if meta and meta["tipo_meta"] == "PERCENTUAL" and meta["base_comparacao"] in TIPOS_COMPARACAO_PRODUTO:
            tipo_comparacao = meta["base_comparacao"]
        else:
            tipo_comparacao = "MESMO_MES_ANO_ANTERIOR"

    grupo_codigos = setores_service.obter_grupos_do_setor(setor_id)
    subgrupos_por_grupo = setores_service.obter_subgrupos_do_setor(setor_id)
    filtros_pdv = dict(
        pdv_incluidos=setor["pdv_incluidos"], pdv_excluidos=setor["pdv_excluidos"],
        dias_semana_excluidos=setor["dias_semana_excluidos"],
    )

    data_ini_atual, data_fim_atual = calculos.periodo_equivalente(ano, mes)
    dias = data_fim_atual.day
    if tipo_comparacao == "MES_ANTERIOR":
        ano_base, mes_base = calculos.mes_anterior(ano, mes)
    else:
        ano_base, mes_base = calculos.mesmo_mes_ano_anterior(ano, mes)
    data_ini_base, data_fim_base = calculos.periodo_equivalente_base(ano_base, mes_base, dias)

    mapa_atual = vendas_service.vendas_por_produto(
        grupo_codigos, data_ini_atual, data_fim_atual, metrica=metrica,
        subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    mapa_base = vendas_service.vendas_por_produto(
        grupo_codigos, data_ini_base, data_fim_base, metrica=metrica,
        subgrupos_por_grupo=subgrupos_por_grupo, **filtros_pdv
    )
    grupos_desc = {g["codigo"]: g["descricao"] for g in vendas_service.listar_grupos_disponiveis()}

    produtos_por_grupo: dict = {}
    for codigo in set(mapa_atual) | set(mapa_base):
        atual = mapa_atual.get(codigo)
        base = mapa_base.get(codigo)
        origem = atual or base
        venda_atual = (atual or {}).get("total", Decimal("0"))
        venda_comparativa = (base or {}).get("total", Decimal("0"))
        variacao_pct = calculos.variacao_percentual(venda_atual, venda_comparativa)
        produtos_por_grupo.setdefault(origem["grupo_codigo"], []).append({
            "codigo": codigo,
            "nome": origem["nome"],
            "venda_atual": str(venda_atual),
            "venda_comparativa": str(venda_comparativa),
            "variacao_valor": str(venda_atual - venda_comparativa),
            "variacao_percentual": str(variacao_pct) if variacao_pct is not None else None,
        })

    grupos_resultado = []
    for grupo_codigo, produtos in produtos_por_grupo.items():
        produtos.sort(key=lambda p: Decimal(p["venda_atual"]), reverse=True)
        venda_atual_grupo = sum((Decimal(p["venda_atual"]) for p in produtos), Decimal("0"))
        venda_comparativa_grupo = sum((Decimal(p["venda_comparativa"]) for p in produtos), Decimal("0"))
        variacao_pct_grupo = calculos.variacao_percentual(venda_atual_grupo, venda_comparativa_grupo)
        grupos_resultado.append({
            "grupo_codigo": grupo_codigo,
            "descricao": grupos_desc.get(grupo_codigo, f"Grupo {grupo_codigo}") if grupo_codigo is not None else "Sem grupo",
            "venda_atual": str(venda_atual_grupo),
            "venda_comparativa": str(venda_comparativa_grupo),
            "variacao_valor": str(venda_atual_grupo - venda_comparativa_grupo),
            "variacao_percentual": str(variacao_pct_grupo) if variacao_pct_grupo is not None else None,
            "produtos": produtos,
        })

    grupos_resultado.sort(key=lambda g: Decimal(g["venda_atual"]), reverse=True)

    return {
        "tipo_comparacao": tipo_comparacao,
        "metrica": metrica,
        "periodo_atual": {"inicio": data_ini_atual.isoformat(), "fim": data_fim_atual.isoformat()},
        "periodo_comparativo": {"inicio": data_ini_base.isoformat(), "fim": data_fim_base.isoformat()},
        "grupos": grupos_resultado,
    }
