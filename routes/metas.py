from datetime import date

from flask import Blueprint, render_template

metas_bp = Blueprint("metas", __name__)


@metas_bp.get("/metas")
def index():
    hoje = date.today()
    return render_template("metas.html", ano_atual=hoje.year, mes_atual=hoje.month)


@metas_bp.get("/configuracoes")
def configuracoes():
    return render_template("configuracoes.html")
