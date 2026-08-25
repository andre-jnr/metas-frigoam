from flask import Blueprint, render_template

setores_bp = Blueprint("setores", __name__)


@setores_bp.get("/setores")
def index():
    return render_template("setores.html")
