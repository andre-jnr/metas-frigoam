import pytest

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
