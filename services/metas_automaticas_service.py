"""Metas automáticas por setor: a meta percentual de cada mês sobe um degrau da escada
(3, 5, 8, 10, 13, 15, 18, 20, 23...) quando o setor bateu a meta do mês anterior e desce
um degrau quando não bateu.

As metas geradas são gravadas na tabela `metas` (automatica = 1) e ficam congeladas: a
sincronização só cria os meses que ainda não existem, do mês de início da regra até o
mês atual. Assim o dashboard consulta o SQL Server só uma vez por mês novo, e quem quiser
ajustar um mês na mão edita a meta normalmente (ela vira manual e a cadeia continua a
partir dela)."""

import threading
from datetime import date

from database.models import BASES_COMPARACAO
from database.sqlite import get_connection
from services import calculos, filiais_service, metas_service, setores_service, vendas_service
from services.errors import ValidationError

MOTIVO_INICIO = "INICIO"
MOTIVO_BATEU = "BATEU"
MOTIVO_NAO_BATEU = "NAO_BATEU"

# Duas requisições ao mesmo tempo (ex.: dashboard aberto em dois computadores no dia 1º)
# gerariam o mesmo mês duas vezes; a sincronização roda uma de cada vez.
_lock_sincronizacao = threading.Lock()


def _proximo_mes(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _regra_to_dict(row) -> dict:
    return {
        "setor_id": row["setor_id"],
        "setor_nome": row["setor_nome"],
        "ano_inicio": row["ano_inicio"],
        "mes_inicio": row["mes_inicio"],
        "percentual_inicial": row["percentual_inicial"],
        "percentual_minimo": row["percentual_minimo"],
        "percentual_maximo": row["percentual_maximo"],
        "base_comparacao": row["base_comparacao"],
    }


def _regras(setor_id: int | None = None, apenas_setores_ativos: bool = False) -> list[dict]:
    sql = """SELECT r.*, s.nome AS setor_nome FROM metas_automaticas r
             JOIN setores s ON s.id = r.setor_id WHERE s.filial_id = ?"""
    params: list = [filiais_service.obter_filial_ativa()["id"]]
    if setor_id is not None:
        sql += " AND r.setor_id = ?"
        params.append(setor_id)
    if apenas_setores_ativos:
        sql += " AND s.ativo = 1"
    sql += " ORDER BY s.ordem_exibicao, s.nome"
    with get_connection() as conn:
        return [_regra_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def obter_regra(setor_id: int) -> dict | None:
    regras = _regras(setor_id)
    return regras[0] if regras else None


def _metas_do_setor(setor_id: int) -> dict[tuple[int, int], dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM metas WHERE setor_id = ?", (setor_id,)).fetchall()
    return {(r["ano"], r["mes"]): dict(r) for r in rows}


def _bateu_meta(setor: dict, meta: dict) -> bool:
    """Venda do mês (mês cheio, mesmos filtros do setor) >= meta final do mês."""
    calc = metas_service.calcular_meta(
        setor["id"], meta["ano"], meta["mes"], meta["tipo_meta"],
        meta["percentual_meta"], meta["valor_meta"], meta["base_comparacao"],
    )
    venda = vendas_service.faturamento_periodo(
        setores_service.obter_grupos_do_setor(setor["id"]),
        *calculos.periodo_do_mes(meta["ano"], meta["mes"]),
        pdv_incluidos=setor["pdv_incluidos"], pdv_excluidos=setor["pdv_excluidos"],
        dias_semana_excluidos=setor["dias_semana_excluidos"],
        subgrupos_por_grupo=setores_service.obter_subgrupos_do_setor(setor["id"]),
    )
    return venda >= calc["valor_meta"]


def sincronizar_regra(regra: dict, hoje: date | None = None) -> int:
    """Cria as metas que faltam do mês de início até o mês atual. Retorna quantas criou."""
    with _lock_sincronizacao:
        return _sincronizar_regra(regra, hoje)


def _sincronizar_regra(regra: dict, hoje: date | None = None) -> int:
    hoje = hoje or date.today()
    setor = setores_service.obter_setor(regra["setor_id"])
    if setor is None:
        return 0
    fim = (hoje.year, hoje.month)
    periodo = (regra["ano_inicio"], regra["mes_inicio"])
    metas = _metas_do_setor(setor["id"])
    percentual = None  # percentual em vigor no mês anterior, para calcular o próximo degrau
    anterior = None
    criadas = 0

    while periodo <= fim:
        meta = metas.get(periodo)
        if meta is None:
            if anterior is None:
                novo, motivo = regra["percentual_inicial"], MOTIVO_INICIO
            else:
                bateu = _bateu_meta(setor, anterior)
                novo = float(calculos.proximo_percentual(
                    percentual, bateu, regra["percentual_minimo"], regra["percentual_maximo"]
                ))
                motivo = MOTIVO_BATEU if bateu else MOTIVO_NAO_BATEU
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO metas (setor_id, ano, mes, tipo_meta, percentual_meta, base_comparacao,
                                          automatica, automatica_motivo)
                       VALUES (?, ?, ?, 'PERCENTUAL', ?, ?, 1, ?)
                       ON CONFLICT(setor_id, ano, mes) DO NOTHING""",
                    (setor["id"], periodo[0], periodo[1], novo, regra["base_comparacao"], motivo),
                )
            meta = {
                "ano": periodo[0], "mes": periodo[1], "tipo_meta": "PERCENTUAL", "percentual_meta": novo,
                "valor_meta": None, "base_comparacao": regra["base_comparacao"],
            }
            criadas += 1

        # meta manual de valor fixo não tem percentual: a escada continua do último degrau
        if meta["tipo_meta"] == "PERCENTUAL":
            percentual = meta["percentual_meta"]
        elif percentual is None:
            percentual = regra["percentual_inicial"]
        anterior = meta
        periodo = _proximo_mes(*periodo)
    return criadas


def sincronizar_todas(hoje: date | None = None) -> int:
    """Chamado ao abrir o dashboard e a lista de metas; só consulta o SQL Server quando
    há mês novo para gerar."""
    return sum(sincronizar_regra(r, hoje) for r in _regras(apenas_setores_ativos=True))


def _historico(regra: dict) -> list[dict]:
    """Metas do setor desde o início da regra, com o resultado de cada mês (lido do
    motivo gravado no mês seguinte; None = mês ainda sem resultado)."""
    metas = _metas_do_setor(regra["setor_id"])
    inicio = (regra["ano_inicio"], regra["mes_inicio"])
    periodos = sorted(p for p in metas if p >= inicio)
    historico = []
    for periodo in periodos:
        meta = metas[periodo]
        seguinte = metas.get(_proximo_mes(*periodo))
        motivo_seguinte = seguinte["automatica_motivo"] if seguinte else None
        historico.append({
            "ano": periodo[0],
            "mes": periodo[1],
            "tipo_meta": meta["tipo_meta"],
            "percentual_meta": meta["percentual_meta"],
            "automatica": bool(meta["automatica"]),
            "motivo": meta["automatica_motivo"],
            "bateu": {MOTIVO_BATEU: True, MOTIVO_NAO_BATEU: False}.get(motivo_seguinte),
        })
    return historico


def listar_regras() -> list[dict]:
    regras = _regras()
    for regra in regras:
        regra["historico"] = _historico(regra)
    return regras


def _validar_percentual(valor, campo: str, obrigatorio: bool = True) -> float | None:
    if valor is None or valor == "":
        if obrigatorio:
            raise ValidationError(f"Informe o {campo}.")
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValidationError(f"{campo.capitalize()} inválido.")
    if not (0 <= numero <= 500):
        raise ValidationError(f"{campo.capitalize()} deve ficar entre 0% e 500%.")
    return numero


def salvar_regra(
    setor_id: int, ano_inicio: int, mes_inicio: int, percentual_inicial, base_comparacao: str,
    percentual_minimo=3, percentual_maximo=None, hoje: date | None = None,
) -> dict:
    """Cria ou substitui a regra do setor e refaz as metas automáticas desde o início
    (metas editadas manualmente são mantidas)."""
    if setores_service.obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    try:
        ano_inicio, mes_inicio = int(ano_inicio), int(mes_inicio)
    except (TypeError, ValueError):
        raise ValidationError("Mês de início inválido.")
    if not (2000 <= ano_inicio <= 2100 and 1 <= mes_inicio <= 12):
        raise ValidationError("Mês de início inválido.")
    if base_comparacao not in BASES_COMPARACAO or base_comparacao == "NAO_APLICAVEL":
        raise ValidationError("Selecione o período comparativo (mesmo mês do ano anterior ou mês anterior).")
    inicial = _validar_percentual(percentual_inicial, "percentual inicial")
    minimo = _validar_percentual(percentual_minimo, "percentual mínimo")
    maximo = _validar_percentual(percentual_maximo, "percentual máximo", obrigatorio=False)
    if maximo is not None and maximo < minimo:
        raise ValidationError("O percentual máximo não pode ser menor que o mínimo.")
    if inicial < minimo or (maximo is not None and inicial > maximo):
        raise ValidationError("O percentual inicial precisa ficar entre o mínimo e o máximo.")

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO metas_automaticas (setor_id, ano_inicio, mes_inicio, percentual_inicial,
                                              percentual_minimo, percentual_maximo, base_comparacao)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(setor_id) DO UPDATE SET
                   ano_inicio = excluded.ano_inicio, mes_inicio = excluded.mes_inicio,
                   percentual_inicial = excluded.percentual_inicial,
                   percentual_minimo = excluded.percentual_minimo,
                   percentual_maximo = excluded.percentual_maximo,
                   base_comparacao = excluded.base_comparacao, updated_at = datetime('now')""",
            (setor_id, ano_inicio, mes_inicio, inicial, minimo, maximo, base_comparacao),
        )
        conn.execute("DELETE FROM metas WHERE setor_id = ? AND automatica = 1", (setor_id,))

    regra = obter_regra(setor_id)
    sincronizar_regra(regra, hoje)
    regra["historico"] = _historico(regra)
    return regra


def excluir_regra(setor_id: int) -> None:
    """Para de gerar metas para o setor. As metas já geradas continuam cadastradas."""
    if obter_regra(setor_id) is None:
        raise ValidationError("Este setor não tem meta automática.", status_code=404)
    with get_connection() as conn:
        conn.execute("DELETE FROM metas_automaticas WHERE setor_id = ?", (setor_id,))
