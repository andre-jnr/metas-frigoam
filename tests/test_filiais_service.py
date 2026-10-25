import pytest

from config import Config, filtrar_filiais
from services import filiais_service as fs
from services.errors import ValidationError


def test_obter_filial_ativa_default_e_primeira_da_lista(temp_db):
    filial = fs.obter_filial_ativa()
    assert filial["id"] == "pn"
    assert filial["nome"] == "Ponta Negra"


def test_listar_filiais_marca_ativa(temp_db):
    filiais = fs.listar_filiais()
    ids = {f["id"] for f in filiais}
    assert ids == {"pn", "prq10", "ad"}
    ativas = [f["id"] for f in filiais if f["ativa"]]
    assert ativas == ["pn"]


def test_filial_morada_do_sol_tem_banco_proprio(temp_db):
    filiais = {f["id"]: f for f in fs.listar_filiais()}
    assert filiais["ad"]["nome"] == "Morada do Sol"
    assert filiais["ad"]["banco"] == "sismoura_srv"
    # pn/prq10 continuam no mesmo banco compartilhado
    assert filiais["pn"]["banco"] == filiais["prq10"]["banco"] == "sismoura"


def test_definir_filial_ativa_persiste(temp_db):
    fs.definir_filial_ativa("prq10")
    assert fs.obter_filial_ativa()["id"] == "prq10"
    filiais = fs.listar_filiais()
    ativas = [f["id"] for f in filiais if f["ativa"]]
    assert ativas == ["prq10"]


def test_definir_filial_ativa_invalida_gera_validation_error(temp_db):
    with pytest.raises(ValidationError):
        fs.definir_filial_ativa("inexistente")


def test_definir_filial_ativa_troca_de_volta(temp_db):
    fs.definir_filial_ativa("prq10")
    fs.definir_filial_ativa("pn")
    assert fs.obter_filial_ativa()["id"] == "pn"


def test_filtrar_filiais_vazio_mantem_todas():
    assert [f["id"] for f in filtrar_filiais(Config.TODAS_FILIAIS, "")] == ["pn", "prq10", "ad"]


def test_filtrar_filiais_respeita_lista_e_ordem():
    filiais = filtrar_filiais(Config.TODAS_FILIAIS, " AD , pn,ad")
    assert [f["id"] for f in filiais] == ["ad", "pn"]


def test_filtrar_filiais_desconhecida_gera_erro():
    with pytest.raises(ValueError, match="xyz"):
        filtrar_filiais(Config.TODAS_FILIAIS, "pn,xyz")


def test_filiais_ativas_restringe_seletor_e_troca(temp_db, monkeypatch):
    fs.definir_filial_ativa("prq10")
    monkeypatch.setattr(Config, "FILIAIS", filtrar_filiais(Config.TODAS_FILIAIS, "pn"))
    # a filial salva saiu da lista: volta para a primeira liberada
    assert fs.obter_filial_ativa()["id"] == "pn"
    assert [f["id"] for f in fs.listar_filiais()] == ["pn"]
    with pytest.raises(ValidationError):
        fs.definir_filial_ativa("ad")
