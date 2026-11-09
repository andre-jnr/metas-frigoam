import pytest

from config import Config
from services import auth_service, dashboard_service, permissoes
from services.errors import ValidationError

DASHBOARD = {
    "resumo": {"faturamento_total": "1000.00", "meta_total": "2000.00", "percentual_total": "50.00",
               "setores_no_ritmo": 1, "setores_abaixo": 0, "metas_batidas": 0, "total_setores": 1},
    "setores": [{"id": 1, "nome": "Padaria", "meta_final": "2000.00", "venda_realizada": "1000.00",
                 "venda_base": "1800.00", "valor_esperado": "900.00", "percentual_realizado": "50.00",
                 "percentual_esperado": "45.00", "diferenca": "5.00", "status": "NO_RITMO"}],
    "ano": 2026, "mes": 11, "atualizado_em": "2026-11-04T10:00:00",
}

SETOR = {
    "setor": {"id": 1, "nome": "Padaria", "descricao": ""}, "ano": 2026, "mes": 11, "tem_meta": True,
    "meta_final": "2000.00", "venda_realizada": "1000.00", "venda_base": "1800.00", "valor_esperado": "900.00",
    "percentual_realizado": "50.00", "percentual_esperado": "45.00", "diferenca": "5.00", "status": "NO_RITMO",
    "estrela": True,
    "evolucao_diaria": [{"dia": "2026-11-01", "valor": "500.00", "acumulado": "500.00", "meta_acumulada": "66.67"}],
    "ranking_grupos": [{"descricao": "PAES", "total": "750.00"}, {"descricao": "BOLOS", "total": "250.00"}],
    "comparacao": {"venda_mes_anterior": "800.00", "venda_mesmo_mes_ano_anterior": "0"},
}


@pytest.fixture
def app(temp_db, monkeypatch):
    monkeypatch.setattr(Config, "ADMIN_USUARIO", "andre")
    monkeypatch.setattr(Config, "ADMIN_SENHA", "senha-admin")
    monkeypatch.setattr(Config, "SECRET_KEY", "chave-de-teste")
    auth_service._falhas.clear()
    monkeypatch.setattr(dashboard_service, "montar_dashboard", lambda *a, **k: DASHBOARD)
    monkeypatch.setattr(dashboard_service, "montar_dashboard_setor", lambda *a, **k: SETOR)
    from app import create_app

    return create_app()


def _cliente(app, usuario, senha):
    client = app.test_client()
    assert client.post("/login", data={"usuario": usuario, "senha": senha}).status_code == 302
    return client


@pytest.fixture
def admin(app):
    return _cliente(app, "andre", "senha-admin")


@pytest.fixture
def so_percentual(app, admin):
    assert admin.post("/api/usuarios", json={"usuario": "maria", "senha": "123456", "pode_ver_valores": False}).status_code == 201
    return _cliente(app, "maria", "123456")


def test_superusuario_ve_a_aba_de_usuarios(admin):
    pagina = admin.get("/").get_data(as_text=True)
    assert 'href="/usuarios"' in pagina
    assert admin.get("/usuarios").status_code == 200


def test_usuario_comum_nao_cadastra_usuarios(so_percentual):
    assert 'href="/usuarios"' not in so_percentual.get("/").get_data(as_text=True)
    assert so_percentual.get("/api/usuarios").status_code == 403
    assert so_percentual.post("/api/usuarios", json={"usuario": "x", "senha": "123456"}).status_code == 403
    assert so_percentual.get("/api/backup/exportar").status_code == 403


def test_so_percentual_perde_valores_e_metas(so_percentual):
    pagina = so_percentual.get("/").get_data(as_text=True)
    assert 'href="/valores"' not in pagina
    assert 'href="/metas"' not in pagina
    assert 'id="ocultar-valores-btn"' not in pagina
    assert "somente-percentual" in pagina
    assert so_percentual.get("/valores").status_code == 302
    assert so_percentual.get("/metas").status_code == 302
    assert so_percentual.get("/api/metas").status_code == 403
    assert so_percentual.get("/api/metas-automaticas").status_code == 403


def test_so_percentual_recebe_dashboard_sem_reais(so_percentual):
    dados = so_percentual.get("/api/dashboard").get_json()
    assert dados["somente_percentual"] is True
    assert dados["resumo"]["faturamento_total"] is None
    setor = dados["setores"][0]
    assert setor["venda_realizada"] is None and setor["meta_final"] is None
    assert setor["percentual_realizado"] == "50.00"
    assert "1000.00" not in str(dados)


def test_quem_ve_valores_recebe_tudo(admin):
    assert admin.get("/api/dashboard").get_json()["resumo"]["faturamento_total"] == "1000.00"


def test_setor_em_porcentagem():
    dados = permissoes.setor_sem_valores(SETOR)
    assert dados["venda_realizada"] is None
    assert dados["evolucao_diaria"] == [{"dia": "2026-11-01", "acumulado_pct": "25.00", "meta_acumulada_pct": "3.33"}]
    assert [r["participacao_pct"] for r in dados["ranking_grupos"]] == ["75.00", "25.00"]
    assert "total" not in dados["ranking_grupos"][0]
    assert dados["comparacao"] == {"variacao_mes_anterior_pct": "25.00", "variacao_mesmo_mes_ano_anterior_pct": None}
    assert SETOR["venda_realizada"] == "1000.00"  # não altera o original (fica em cache)


def test_produtos_so_por_quantidade(so_percentual, monkeypatch):
    pedidos = []
    monkeypatch.setattr(dashboard_service, "montar_produtos_setor", lambda *a: pedidos.append(a[4]) or {})
    so_percentual.get("/api/dashboard/setor/1/produtos?metrica=valor")
    assert pedidos == ["quantidade"]


def test_mudanca_de_permissao_vale_na_hora(app, admin, so_percentual):
    maria = next(u for u in admin.get("/api/usuarios").get_json() if u["usuario"] == "maria")
    admin.put(f"/api/usuarios/{maria['id']}", json={"pode_ver_valores": True, "superusuario": False, "ativo": True})
    assert so_percentual.get("/api/dashboard").get_json()["resumo"]["faturamento_total"] == "1000.00"
    admin.put(f"/api/usuarios/{maria['id']}", json={"pode_ver_valores": True, "superusuario": False, "ativo": False})
    assert so_percentual.get("/api/dashboard").status_code == 401


def test_trocar_senha_derruba_a_sessao_do_usuario(admin, so_percentual):
    maria = next(u for u in admin.get("/api/usuarios").get_json() if u["usuario"] == "maria")
    admin.put(f"/api/usuarios/{maria['id']}", json={"pode_ver_valores": False, "ativo": True, "senha": "nova-senha"})
    assert so_percentual.get("/api/dashboard").status_code == 401


def test_superusuario_do_env_e_protegido(admin):
    andre = next(u for u in admin.get("/api/usuarios").get_json() if u["usuario"] == "andre")
    assert andre["do_env"] is True
    resp = admin.put(f"/api/usuarios/{andre['id']}", json={"pode_ver_valores": True, "superusuario": False, "ativo": True})
    assert resp.status_code == 400
    assert admin.delete(f"/api/usuarios/{andre['id']}").status_code == 400


def test_validacoes_do_cadastro(temp_db):
    with pytest.raises(ValidationError):
        auth_service.criar_usuario("a", "123456", True)  # nome curto
    with pytest.raises(ValidationError):
        auth_service.criar_usuario("joao", "123", True)  # senha curta
    auth_service.criar_usuario("joao", "123456", False)
    with pytest.raises(ValidationError):
        auth_service.criar_usuario("JOAO", "123456", False)  # já existe (maiúsculas não contam)


def test_superusuario_sempre_ve_valores(temp_db):
    novo = auth_service.criar_usuario("chefe", "123456", pode_ver_valores=False, superusuario=True)
    assert novo["pode_ver_valores"] is True


def test_formato_dos_valores_e_por_usuario(admin, so_percentual):
    assert 'formatoValores: "2"' in admin.get("/configuracoes").get_data(as_text=True)  # padrão: 2 casas
    assert admin.put("/api/preferencias", json={"formato_valores": "inteiro"}).get_json() == {"formato_valores": "inteiro"}
    pagina = admin.get("/configuracoes").get_data(as_text=True)
    assert 'formatoValores: "inteiro"' in pagina
    assert "valores-inteiros" in pagina
    assert admin.put("/api/preferencias", json={"formato_valores": "5"}).status_code == 400
    # a escolha de um usuário não muda a do outro
    assert 'formatoValores: "2"' in so_percentual.get("/").get_data(as_text=True)


def test_quem_so_ve_porcentagens_nao_ve_o_card_de_formato(admin, so_percentual):
    assert 'id="formato-previa"' in admin.get("/configuracoes").get_data(as_text=True)
    assert 'id="formato-previa"' not in so_percentual.get("/configuracoes").get_data(as_text=True)
