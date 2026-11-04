import time

import pytest

from config import Config
from services import auth_service


@pytest.fixture
def client(temp_db, monkeypatch):
    monkeypatch.setattr(Config, "ADMIN_USUARIO", "andre")
    monkeypatch.setattr(Config, "ADMIN_SENHA", "senha-de-teste")
    monkeypatch.setattr(Config, "SECRET_KEY", "chave-de-teste")
    auth_service._falhas.clear()
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _entrar(client, senha="senha-de-teste", usuario="andre", **extra):
    return client.post("/login", data={"usuario": usuario, "senha": senha, **extra})


def test_pagina_sem_login_vai_para_o_login(client):
    resp = client.get("/metas")
    assert resp.status_code == 302
    assert "/login?next=/metas" in resp.headers["Location"]


def test_api_sem_login_responde_401(client):
    resp = client.get("/api/setores")
    assert resp.status_code == 401
    assert resp.get_json()["login"] is True


def test_tela_de_login_fica_aberta(client):
    assert client.get("/login").status_code == 200


def test_login_correto_abre_o_sistema_e_volta_para_a_pagina_pedida(client):
    resp = _entrar(client, next="/metas")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/metas")
    assert client.get("/api/setores").status_code == 200
    assert client.get("/api/sessao").get_json()["usuario"] == "andre"


def test_usuario_nao_diferencia_maiusculas(client):
    assert _entrar(client, usuario=" Andre ").status_code == 302


def test_senha_errada_nao_entra(client):
    resp = _entrar(client, senha="errada")
    assert resp.status_code == 401
    assert "incorretos" in resp.get_data(as_text=True)
    assert client.get("/api/setores").status_code == 401


def test_next_para_outro_site_e_ignorado(client):
    resp = _entrar(client, next="https://exemplo.com/roubo")
    assert resp.headers["Location"].endswith("/")


def test_bloqueia_depois_de_cinco_tentativas_erradas(client):
    for _ in range(auth_service.MAX_FALHAS):
        _entrar(client, senha="errada")
    resp = _entrar(client)  # mesmo com a senha certa, fica bloqueado
    assert resp.status_code == 429
    assert "Muitas tentativas" in resp.get_data(as_text=True)


def test_sessao_expira_depois_de_8_horas(client, monkeypatch):
    _entrar(client)
    agora = time.time()
    monkeypatch.setattr(time, "time", lambda: agora + auth_service.DURACAO_SESSAO.total_seconds() + 1)
    assert client.get("/api/setores").status_code == 401


def test_trocar_a_senha_no_env_derruba_a_sessao(client, monkeypatch):
    _entrar(client)
    monkeypatch.setattr(Config, "ADMIN_SENHA", "nova-senha")
    auth_service.garantir_superusuario()
    assert client.get("/api/setores").status_code == 401


def test_logout_encerra_a_sessao(client):
    _entrar(client)
    assert client.post("/logout").status_code == 302
    assert client.get("/api/setores").status_code == 401


def test_senha_fica_so_como_hash(client):
    from database.sqlite import get_connection

    with get_connection() as conn:
        senha_hash = conn.execute("SELECT senha_hash FROM usuarios WHERE usuario = 'andre'").fetchone()[0]
    assert "senha-de-teste" not in senha_hash
