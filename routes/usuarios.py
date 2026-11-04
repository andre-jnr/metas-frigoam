"""Cadastro de usuários. Só o superusuário chega aqui (regra em routes/auth.py)."""

from flask import Blueprint, g, jsonify, render_template, request

from services import auth_service

usuarios_bp = Blueprint("usuarios", __name__)


@usuarios_bp.get("/usuarios")
def index():
    return render_template("usuarios.html")


@usuarios_bp.get("/api/usuarios")
def listar():
    return jsonify(auth_service.listar_usuarios())


@usuarios_bp.post("/api/usuarios")
def criar():
    body = request.get_json(force=True, silent=True) or {}
    usuario = auth_service.criar_usuario(
        body.get("usuario"), body.get("senha"),
        bool(body.get("pode_ver_valores", False)), bool(body.get("superusuario", False)),
    )
    return jsonify(usuario), 201


@usuarios_bp.put("/api/usuarios/<int:usuario_id>")
def atualizar(usuario_id):
    body = request.get_json(force=True, silent=True) or {}
    usuario = auth_service.atualizar_usuario(
        usuario_id, g.usuario,
        bool(body.get("pode_ver_valores", False)), bool(body.get("superusuario", False)),
        bool(body.get("ativo", True)), body.get("senha") or None,
    )
    return jsonify(usuario)


@usuarios_bp.delete("/api/usuarios/<int:usuario_id>")
def excluir(usuario_id):
    auth_service.excluir_usuario(usuario_id, g.usuario)
    return "", 204
