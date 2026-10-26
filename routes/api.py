from datetime import date, datetime

from flask import Blueprint, jsonify, request

from database.sql_server import testar_conexao
from database.sqlite import get_connection
from services import (
    backup_service, dashboard_service, filiais_service, metas_automaticas_service, metas_service,
    setores_service, vendas_service,
)
from services.errors import ValidationError

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _int_arg(name: str, default=None):
    val = request.args.get(name, default)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        raise ValidationError(f"Parâmetro '{name}' inválido.")


@api_bp.get("/filiais")
def listar_filiais():
    return jsonify(filiais_service.listar_filiais())


@api_bp.post("/filiais/ativa")
def definir_filial_ativa():
    body = request.get_json(force=True, silent=True) or {}
    filial = filiais_service.definir_filial_ativa(body.get("filial_id"))
    dashboard_service.invalidar_cache()
    return jsonify(filial)


@api_bp.get("/health")
def health():
    sql_ok = testar_conexao()
    sqlite_ok = True
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception:
        sqlite_ok = False
    return jsonify(
        {
            "status": "ok" if sql_ok and sqlite_ok else "degraded",
            "sql_server": sql_ok,
            "sqlite": sqlite_ok,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )


@api_bp.get("/dashboard")
def get_dashboard():
    hoje = date.today()
    ano = _int_arg("ano", hoje.year)
    mes = _int_arg("mes", hoje.month)
    refresh = request.args.get("refresh") in ("1", "true", "True")
    return jsonify(dashboard_service.montar_dashboard(ano, mes, force_refresh=refresh))


@api_bp.get("/dashboard/setor/<int:setor_id>")
def get_dashboard_setor(setor_id):
    hoje = date.today()
    ano = _int_arg("ano", hoje.year)
    mes = _int_arg("mes", hoje.month)
    return jsonify(dashboard_service.montar_dashboard_setor(setor_id, ano, mes))


@api_bp.get("/dashboard/setor/<int:setor_id>/produtos")
def get_produtos_setor(setor_id):
    hoje = date.today()
    ano = _int_arg("ano", hoje.year)
    mes = _int_arg("mes", hoje.month)
    tipo_comparacao = request.args.get("tipo_comparacao")
    metrica = request.args.get("metrica", "valor")
    return jsonify(dashboard_service.montar_produtos_setor(setor_id, ano, mes, tipo_comparacao, metrica))


@api_bp.get("/setores")
def listar_setores():
    apenas_ativos = request.args.get("ativos") == "1"
    return jsonify(setores_service.listar_setores(apenas_ativos=apenas_ativos))


@api_bp.get("/setores/<int:setor_id>")
def obter_setor(setor_id):
    setor = setores_service.obter_setor(setor_id)
    if setor is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    setor["grupo_codigos"] = setores_service.obter_grupos_do_setor(setor_id)
    setor["subgrupos_por_grupo"] = setores_service.obter_subgrupos_do_setor(setor_id)
    return jsonify(setor)


@api_bp.post("/setores")
def criar_setor():
    body = request.get_json(force=True, silent=True) or {}
    setor = setores_service.criar_setor(
        body.get("nome"), body.get("descricao", ""), body.get("ordem_exibicao", 0),
        body.get("pdv_incluidos"), body.get("pdv_excluidos"), body.get("dias_semana_excluidos"),
    )
    if body.get("grupo_codigos") is not None:
        grupo_codigos = setores_service.definir_grupos_do_setor(setor["id"], body["grupo_codigos"])
        if body.get("subgrupos_por_grupo") is not None:
            setores_service.definir_subgrupos_do_setor(setor["id"], body["subgrupos_por_grupo"], grupo_codigos)
        setor = setores_service.obter_setor(setor["id"])
    dashboard_service.invalidar_cache()
    return jsonify(setor), 201


@api_bp.put("/setores/<int:setor_id>")
def atualizar_setor(setor_id):
    body = request.get_json(force=True, silent=True) or {}
    setor = setores_service.atualizar_setor(
        setor_id, body.get("nome"), body.get("descricao", ""), body.get("ordem_exibicao", 0),
        body.get("pdv_incluidos"), body.get("pdv_excluidos"), body.get("dias_semana_excluidos"),
    )
    if body.get("grupo_codigos") is not None:
        grupo_codigos = setores_service.definir_grupos_do_setor(setor_id, body["grupo_codigos"])
        if body.get("subgrupos_por_grupo") is not None:
            setores_service.definir_subgrupos_do_setor(setor_id, body["subgrupos_por_grupo"], grupo_codigos)
        setor = setores_service.obter_setor(setor_id)
    dashboard_service.invalidar_cache()
    return jsonify(setor)


@api_bp.patch("/setores/<int:setor_id>/ativo")
def alternar_ativo_setor(setor_id):
    body = request.get_json(force=True, silent=True) or {}
    setor = setores_service.alternar_ativo(setor_id, bool(body.get("ativo", True)))
    dashboard_service.invalidar_cache()
    return jsonify(setor)


@api_bp.delete("/setores/<int:setor_id>")
def excluir_setor(setor_id):
    setores_service.excluir_setor(setor_id)
    dashboard_service.invalidar_cache()
    return "", 204


@api_bp.get("/setores/<int:setor_id>/grupos")
def get_grupos_setor(setor_id):
    return jsonify(setores_service.obter_grupos_do_setor(setor_id))


@api_bp.post("/setores/<int:setor_id>/grupos")
def set_grupos_setor(setor_id):
    body = request.get_json(force=True, silent=True) or {}
    codigos = setores_service.definir_grupos_do_setor(setor_id, body.get("grupo_codigos", []))
    dashboard_service.invalidar_cache()
    return jsonify(codigos)


@api_bp.get("/setores/<int:setor_id>/subgrupos")
def get_subgrupos_setor(setor_id):
    return jsonify(setores_service.obter_subgrupos_do_setor(setor_id))


@api_bp.post("/setores/<int:setor_id>/subgrupos")
def set_subgrupos_setor(setor_id):
    body = request.get_json(force=True, silent=True) or {}
    grupo_codigos = setores_service.obter_grupos_do_setor(setor_id)
    mapa = setores_service.definir_subgrupos_do_setor(
        setor_id, body.get("subgrupos_por_grupo", {}), grupo_codigos
    )
    dashboard_service.invalidar_cache()
    return jsonify(mapa)


@api_bp.get("/grupos")
def listar_grupos():
    return jsonify(vendas_service.listar_grupos_disponiveis())


@api_bp.get("/subgrupos")
def listar_subgrupos():
    return jsonify(vendas_service.listar_subgrupos_disponiveis())


@api_bp.get("/grupos-subgrupos")
def listar_grupos_subgrupos():
    return jsonify(vendas_service.listar_subgrupos_por_grupo())


@api_bp.get("/pdvs")
def listar_pdvs():
    return jsonify(vendas_service.listar_pdvs_disponiveis())


@api_bp.get("/metas")
def listar_metas():
    setor_id = _int_arg("setor_id")
    ano = _int_arg("ano")
    mes = _int_arg("mes")
    metas_automaticas_service.sincronizar_todas()
    return jsonify(metas_service.listar_metas(setor_id, ano, mes))


@api_bp.get("/metas/preview")
def preview_meta():
    setor_id = _int_arg("setor_id")
    ano = _int_arg("ano")
    mes = _int_arg("mes")
    tipo_meta = request.args.get("tipo_meta")
    percentual = request.args.get("percentual_meta", type=float)
    valor = request.args.get("valor_meta", type=float)
    base = request.args.get("base_comparacao", "NAO_APLICAVEL")
    if not setor_id or not ano or not mes or not tipo_meta:
        raise ValidationError("Parâmetros obrigatórios: setor_id, ano, mes, tipo_meta.")
    calc = metas_service.calcular_meta(setor_id, ano, mes, tipo_meta, percentual, valor, base)
    return jsonify(
        {
            "valor_meta": str(calc["valor_meta"]),
            "venda_base": str(calc["venda_base"]) if calc["venda_base"] is not None else None,
            "tem_dados": calc["tem_dados"],
        }
    )


@api_bp.get("/metas/<int:meta_id>")
def obter_meta(meta_id):
    meta = metas_service.obter_meta(meta_id)
    if meta is None:
        raise ValidationError("Meta não encontrada.", status_code=404)
    return jsonify(meta)


@api_bp.post("/metas")
def criar_meta():
    body = request.get_json(force=True, silent=True) or {}
    meta = metas_service.criar_meta(
        body.get("setor_id"),
        body.get("ano"),
        body.get("mes"),
        body.get("tipo_meta"),
        body.get("percentual_meta"),
        body.get("valor_meta"),
        body.get("base_comparacao", "NAO_APLICAVEL"),
        bool(body.get("confirmar_zero", False)),
    )
    dashboard_service.invalidar_cache()
    return jsonify(meta), 201


@api_bp.put("/metas/<int:meta_id>")
def atualizar_meta(meta_id):
    body = request.get_json(force=True, silent=True) or {}
    meta = metas_service.atualizar_meta(
        meta_id,
        body.get("setor_id"),
        body.get("ano"),
        body.get("mes"),
        body.get("tipo_meta"),
        body.get("percentual_meta"),
        body.get("valor_meta"),
        body.get("base_comparacao", "NAO_APLICAVEL"),
        bool(body.get("confirmar_zero", False)),
    )
    dashboard_service.invalidar_cache()
    return jsonify(meta)


@api_bp.patch("/metas/<int:meta_id>/ativo")
def alternar_ativo_meta(meta_id):
    body = request.get_json(force=True, silent=True) or {}
    meta = metas_service.alternar_ativo(meta_id, bool(body.get("ativo", True)))
    dashboard_service.invalidar_cache()
    return jsonify(meta)


@api_bp.delete("/metas/<int:meta_id>")
def excluir_meta(meta_id):
    metas_service.excluir_meta(meta_id)
    dashboard_service.invalidar_cache()
    return "", 204


@api_bp.get("/backup/exportar")
def exportar_backup():
    resp = jsonify(backup_service.exportar())
    nome = f"backup_metas_{datetime.now():%Y-%m-%d_%H%M}.json"
    resp.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resp


@api_bp.post("/backup/importar")
def importar_backup():
    body = request.get_json(force=True, silent=True)
    if body is None:
        raise ValidationError("Arquivo inválido: o conteúdo não é um JSON válido.")
    resumo = backup_service.importar(body)
    dashboard_service.invalidar_cache()
    return jsonify(resumo)


@api_bp.get("/metas-automaticas")
def listar_metas_automaticas():
    metas_automaticas_service.sincronizar_todas()
    return jsonify(metas_automaticas_service.listar_regras())


@api_bp.put("/metas-automaticas/<int:setor_id>")
def salvar_meta_automatica(setor_id):
    body = request.get_json(force=True, silent=True) or {}
    regra = metas_automaticas_service.salvar_regra(
        setor_id, body.get("ano_inicio"), body.get("mes_inicio"), body.get("percentual_inicial"),
        body.get("base_comparacao"), body.get("percentual_minimo", 3), body.get("percentual_maximo"),
    )
    dashboard_service.invalidar_cache()
    return jsonify(regra)


@api_bp.delete("/metas-automaticas/<int:setor_id>")
def excluir_meta_automatica(setor_id):
    metas_automaticas_service.excluir_regra(setor_id)
    dashboard_service.invalidar_cache()
    return "", 204
