import time
from urllib.parse import urlparse

from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for

from services import auth_service

auth_bp = Blueprint("auth", __name__)

# Abertas sem login: a própria tela de login, os arquivos estáticos e o /api/health
# (usado para monitorar se o sistema está no ar).
ROTAS_PUBLICAS = {"auth.login", "auth.logout", "static", "api.health"}

# Caminhos só do superusuário: cadastro de usuários e backup (o arquivo leva todos os valores).
CAMINHOS_SUPERUSUARIO = ("/usuarios", "/api/usuarios", "/api/backup")
# Caminhos que mostram valores em R$ e somem para quem só vê porcentagens. O dashboard e
# o detalhe do setor continuam abertos, mas a API tira os valores (routes/api.py).
CAMINHOS_COM_VALORES = ("/valores", "/metas", "/api/metas", "/api/metas-automaticas")


def _no_caminho(caminho: str, prefixos: tuple[str, ...]) -> bool:
    return any(caminho == p or caminho.startswith(p + "/") for p in prefixos)


def _negar(mensagem: str):
    if request.path.startswith("/api/"):
        return jsonify({"erro": mensagem}), 403
    return redirect(url_for("dashboard.index"))


def _destino_seguro(destino: str | None) -> str:
    """Só aceita caminhos deste sistema (evita mandar o usuário para outro site)."""
    if not destino:
        return url_for("dashboard.index")
    partes = urlparse(destino)
    if partes.scheme or partes.netloc or not destino.startswith("/") or destino.startswith("//"):
        return url_for("dashboard.index")
    return destino


@auth_bp.before_app_request
def exigir_login():
    dados = session.get("auth")
    atual = auth_service.usuario_da_sessao(dados)
    if atual:
        g.usuario = atual["usuario"]
        g.superusuario = atual["superusuario"]
        g.pode_ver_valores = atual["pode_ver_valores"]
        g.formato_valores = atual["formato_valores"]
        g.sessao_expira_em = atual["expira_em"]
        if _no_caminho(request.path, CAMINHOS_SUPERUSUARIO) and not g.superusuario:
            return _negar("Apenas superusuários podem acessar esta área.")
        if _no_caminho(request.path, CAMINHOS_COM_VALORES) and not g.pode_ver_valores:
            return _negar("Seu usuário vê apenas porcentagens.")
        return None
    g.usuario = None
    g.superusuario = False
    g.pode_ver_valores = False
    g.formato_valores = auth_service.FORMATO_PADRAO
    if dados:
        session.clear()
    if request.endpoint in ROTAS_PUBLICAS:
        return None
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Sua sessão expirou. Entre novamente.", "login": True}), 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


@auth_bp.app_context_processor
def usuario_no_template():
    return {
        "usuario_logado": getattr(g, "usuario", None),
        "eh_superusuario": getattr(g, "superusuario", False),
        "pode_ver_valores": getattr(g, "pode_ver_valores", False),
        "formato_valores": getattr(g, "formato_valores", auth_service.FORMATO_PADRAO),
    }


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    destino = _destino_seguro(request.values.get("next"))
    if getattr(g, "usuario", None):
        return redirect(destino)

    erro = None
    usuario = ""
    origem = request.remote_addr or "desconhecido"
    bloqueado = auth_service.segundos_bloqueado(origem)

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        if bloqueado:
            erro = f"Muitas tentativas. Tente de novo em {max(1, round(bloqueado / 60))} min."
        else:
            dados = auth_service.autenticar(usuario, request.form.get("senha") or "", origem)
            if dados:
                session.clear()
                session.permanent = True
                session["auth"] = dados
                return redirect(destino)
            bloqueado = auth_service.segundos_bloqueado(origem)
            erro = (
                f"Muitas tentativas. Tente de novo em {max(1, round(bloqueado / 60))} min."
                if bloqueado else "Usuário ou senha incorretos."
            )

    status = 429 if bloqueado else (401 if erro else 200)
    return render_template(
        "login.html",
        erro=erro,
        usuario=usuario,
        destino=destino,
        sem_usuario=not auth_service.existe_usuario(),
        horas_sessao=auth_service.SESSAO_HORAS,
    ), status


@auth_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.get("/api/sessao")
def sessao():
    restante = max(0, int(getattr(g, "sessao_expira_em", time.time()) - time.time()))
    return jsonify({
        "usuario": g.usuario, "superusuario": g.superusuario, "pode_ver_valores": g.pode_ver_valores,
        "segundos_restantes": restante,
    })


@auth_bp.put("/api/preferencias")
def salvar_preferencias():
    """Preferências de exibição do próprio usuário (cada um escolhe a sua)."""
    body = request.get_json(force=True, silent=True) or {}
    formato = auth_service.definir_formato_valores(g.usuario, body.get("formato_valores"))
    return jsonify({"formato_valores": formato})
