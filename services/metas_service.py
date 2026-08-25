"""CRUD de metas + cálculo/preview de meta percentual (seções 9-12, 39-40, 55)."""

import sqlite3
from decimal import Decimal

from database.models import TIPOS_META
from database.sqlite import get_connection
from services import calculos, filiais_service, setores_service, vendas_service
from services.errors import ValidationError


def _periodo_base(ano: int, mes: int, base_comparacao: str):
    if base_comparacao == "MES_ANTERIOR":
        ano_b, mes_b = calculos.mes_anterior(ano, mes)
    elif base_comparacao == "MESMO_MES_ANO_ANTERIOR":
        ano_b, mes_b = calculos.mesmo_mes_ano_anterior(ano, mes)
    else:
        raise ValidationError("Base de comparação inválida para meta percentual.")
    return calculos.periodo_do_mes(ano_b, mes_b) + ((ano_b, mes_b),)


def calcular_meta(
    setor_id: int,
    ano: int,
    mes: int,
    tipo_meta: str,
    percentual_meta: Decimal | float | None = None,
    valor_meta: Decimal | float | None = None,
    base_comparacao: str = "NAO_APLICAVEL",
) -> dict:
    """Calcula o valor final da meta. Para PERCENTUAL, consulta o SQL Server
    automaticamente — o usuário nunca digita o valor-base (seção 12)."""
    if tipo_meta == "VALOR_FIXO":
        return {"valor_meta": calculos.meta_fixa(valor_meta or 0), "venda_base": None, "tem_dados": True, "periodo_base": None}

    if tipo_meta == "PERCENTUAL":
        grupo_codigos = setores_service.obter_grupos_do_setor(setor_id)
        subgrupos_por_grupo = setores_service.obter_subgrupos_do_setor(setor_id)
        setor = setores_service.obter_setor(setor_id)
        data_ini, data_fim, periodo_base = _periodo_base(ano, mes, base_comparacao)
        venda_base = vendas_service.faturamento_periodo(
            grupo_codigos, data_ini, data_fim,
            pdv_incluidos=setor["pdv_incluidos"] if setor else None,
            pdv_excluidos=setor["pdv_excluidos"] if setor else None,
            dias_semana_excluidos=setor["dias_semana_excluidos"] if setor else None,
            subgrupos_por_grupo=subgrupos_por_grupo,
        )
        tem_dados = venda_base > 0
        valor = calculos.meta_percentual(venda_base, percentual_meta or 0)
        return {"valor_meta": valor, "venda_base": venda_base, "tem_dados": tem_dados, "periodo_base": periodo_base}

    raise ValidationError("Tipo de meta inválido.")


def _validar_periodo(ano: int, mes: int) -> None:
    if not (2000 <= ano <= 2100):
        raise ValidationError("Ano inválido.")
    if not (1 <= mes <= 12):
        raise ValidationError("Mês inválido.")


def _meta_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "setor_id": row["setor_id"],
        "setor_nome": row["setor_nome"] if "setor_nome" in row.keys() else None,
        "ano": row["ano"],
        "mes": row["mes"],
        "tipo_meta": row["tipo_meta"],
        "percentual_meta": row["percentual_meta"],
        "valor_meta": row["valor_meta"],
        "base_comparacao": row["base_comparacao"],
        "ativo": bool(row["ativo"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def listar_metas(setor_id: int | None = None, ano: int | None = None, mes: int | None = None) -> list[dict]:
    sql = """
        SELECT m.*, s.nome AS setor_nome
        FROM metas m JOIN setores s ON s.id = m.setor_id
        WHERE s.filial_id = ?
    """
    params: list = [filiais_service.obter_filial_ativa()["id"]]
    if setor_id is not None:
        sql += " AND m.setor_id = ?"
        params.append(setor_id)
    if ano is not None:
        sql += " AND m.ano = ?"
        params.append(ano)
    if mes is not None:
        sql += " AND m.mes = ?"
        params.append(mes)
    sql += " ORDER BY m.ano DESC, m.mes DESC, s.ordem_exibicao ASC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    resultado = []
    for row in rows:
        meta = _meta_row_to_dict(row)
        calc = calcular_meta(
            meta["setor_id"], meta["ano"], meta["mes"], meta["tipo_meta"],
            meta["percentual_meta"], meta["valor_meta"], meta["base_comparacao"],
        )
        meta["valor_calculado"] = str(calc["valor_meta"])
        meta["venda_base"] = str(calc["venda_base"]) if calc["venda_base"] is not None else None
        resultado.append(meta)
    return resultado


def obter_meta(meta_id: int) -> dict | None:
    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        row = conn.execute(
            """SELECT m.*, s.nome AS setor_nome FROM metas m JOIN setores s ON s.id = m.setor_id
               WHERE m.id = ? AND s.filial_id = ?""",
            (meta_id, filial_id),
        ).fetchone()
    return _meta_row_to_dict(row) if row else None


def meta_ativa_do_setor(setor_id: int, ano: int, mes: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM metas WHERE setor_id = ? AND ano = ? AND mes = ? AND ativo = 1",
            (setor_id, ano, mes),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "setor_id": row["setor_id"],
        "ano": row["ano"],
        "mes": row["mes"],
        "tipo_meta": row["tipo_meta"],
        "percentual_meta": row["percentual_meta"],
        "valor_meta": row["valor_meta"],
        "base_comparacao": row["base_comparacao"],
    }


def metas_ativas_por_setores(setor_ids: list[int], ano: int, mes: int) -> dict[int, dict]:
    if not setor_ids:
        return {}
    with get_connection() as conn:
        placeholders = ",".join("?" * len(setor_ids))
        rows = conn.execute(
            f"""SELECT * FROM metas WHERE ano = ? AND mes = ? AND ativo = 1
                AND setor_id IN ({placeholders})""",
            (ano, mes, *setor_ids),
        ).fetchall()
    return {r["setor_id"]: dict(r) for r in rows}


def _validar_payload(setor_id, ano, mes, tipo_meta, percentual_meta, valor_meta, base_comparacao, confirmar_zero):
    if setores_service.obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    _validar_periodo(ano, mes)
    if tipo_meta not in TIPOS_META:
        raise ValidationError("Tipo de meta inválido.")

    if tipo_meta == "VALOR_FIXO":
        if valor_meta is None or Decimal(str(valor_meta)) <= 0:
            raise ValidationError("Informe um valor de meta maior que zero.")
        base_comparacao = "NAO_APLICAVEL"
        percentual_meta = None
        valor_final = calculos.meta_fixa(valor_meta)
    else:
        if percentual_meta is None:
            raise ValidationError("Informe o percentual de crescimento desejado.")
        if base_comparacao not in ("MESMO_MES_ANO_ANTERIOR", "MES_ANTERIOR"):
            raise ValidationError("Selecione a base de comparação (mesmo mês do ano anterior ou mês anterior).")
        calc = calcular_meta(setor_id, ano, mes, tipo_meta, percentual_meta, None, base_comparacao)
        if not calc["tem_dados"] and not confirmar_zero:
            raise ValidationError(
                "Não foi possível calcular automaticamente a meta: não existem vendas registradas "
                "no período de comparação. Confirme explicitamente para usar R$ 0,00 como base.",
                status_code=422,
            )
        valor_final = None  # calculado dinamicamente a cada consulta, não congelado

    return {
        "tipo_meta": tipo_meta,
        "percentual_meta": float(percentual_meta) if percentual_meta is not None else None,
        "valor_meta": float(valor_final) if valor_final is not None else None,
        "base_comparacao": base_comparacao,
    }


def criar_meta(
    setor_id: int, ano: int, mes: int, tipo_meta: str,
    percentual_meta=None, valor_meta=None, base_comparacao="NAO_APLICAVEL", confirmar_zero=False,
) -> dict:
    dados = _validar_payload(setor_id, ano, mes, tipo_meta, percentual_meta, valor_meta, base_comparacao, confirmar_zero)
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO metas (setor_id, ano, mes, tipo_meta, percentual_meta, valor_meta, base_comparacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (setor_id, ano, mes, dados["tipo_meta"], dados["percentual_meta"], dados["valor_meta"], dados["base_comparacao"]),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Já existe uma meta cadastrada para este setor neste período.") from exc
        meta_id = cursor.lastrowid
    return obter_meta(meta_id)


def atualizar_meta(
    meta_id: int, setor_id: int, ano: int, mes: int, tipo_meta: str,
    percentual_meta=None, valor_meta=None, base_comparacao="NAO_APLICAVEL", confirmar_zero=False,
) -> dict:
    if obter_meta(meta_id) is None:
        raise ValidationError("Meta não encontrada.", status_code=404)
    dados = _validar_payload(setor_id, ano, mes, tipo_meta, percentual_meta, valor_meta, base_comparacao, confirmar_zero)
    with get_connection() as conn:
        try:
            conn.execute(
                """UPDATE metas SET setor_id=?, ano=?, mes=?, tipo_meta=?, percentual_meta=?,
                   valor_meta=?, base_comparacao=?, updated_at=datetime('now') WHERE id=?""",
                (setor_id, ano, mes, dados["tipo_meta"], dados["percentual_meta"], dados["valor_meta"],
                 dados["base_comparacao"], meta_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Já existe uma meta cadastrada para este setor neste período.") from exc
    return obter_meta(meta_id)


def alternar_ativo(meta_id: int, ativo: bool) -> dict:
    if obter_meta(meta_id) is None:
        raise ValidationError("Meta não encontrada.", status_code=404)
    with get_connection() as conn:
        conn.execute(
            "UPDATE metas SET ativo = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if ativo else 0, meta_id),
        )
    return obter_meta(meta_id)


def excluir_meta(meta_id: int) -> None:
    if obter_meta(meta_id) is None:
        raise ValidationError("Meta não encontrada.", status_code=404)
    with get_connection() as conn:
        conn.execute("DELETE FROM metas WHERE id = ?", (meta_id,))
