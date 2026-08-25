from datetime import date

from flask import Blueprint, render_template

from services.errors import ValidationError
from services.setores_service import obter_setor

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    hoje = date.today()
    return render_template("dashboard.html", ano_atual=hoje.year, mes_atual=hoje.month)


@dashboard_bp.get("/valores")
def index_valores():
    hoje = date.today()
    return render_template("dashboard_valor.html", ano_atual=hoje.year, mes_atual=hoje.month)


@dashboard_bp.get("/setor/<int:setor_id>")
def detalhe_setor(setor_id):
    setor = obter_setor(setor_id)
    if setor is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    hoje = date.today()
    return render_template("setor_detalhe.html", setor=setor, ano_atual=hoje.year, mes_atual=hoje.month)
