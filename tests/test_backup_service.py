import pytest

from database.sqlite import get_connection
from services import backup_service as bs
from services import filiais_service as fs
from services import setores_service as ss
from services.errors import ValidationError


def _inserir_meta(setor_id, ano=2026, mes=1):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO metas (setor_id, ano, mes, tipo_meta, valor_meta, base_comparacao) "
            "VALUES (?, ?, ?, 'VALOR_FIXO', 1000, 'NAO_APLICAVEL')",
            (setor_id, ano, mes),
        )


def _popular():
    setor = ss.criar_setor("Açougue", "Carnes", 1, pdv_excluidos=[5], dias_semana_excluidos=[6])
    ss.definir_grupos_do_setor(setor["id"], [1, 2])
    ss.definir_subgrupos_do_setor(setor["id"], {1: [10, 11]}, [1, 2])
    _inserir_meta(setor["id"])
    fs.definir_filial_ativa("ad")
    ss.criar_setor("Padaria")
    return setor


def test_exportar_e_importar_restaura_tudo(temp_db):
    setor = _popular()
    backup = bs.exportar()

    with get_connection() as conn:
        for tabela in ("metas", "setor_subgrupo", "setor_grupo", "setores", "app_config"):
            conn.execute(f"DELETE FROM {tabela}")

    resumo = bs.importar(backup)
    assert resumo == {"setores": 2, "setor_grupo": 2, "setor_subgrupo": 2, "metas": 1, "app_config": 1}
    assert bs.exportar()["dados"] == backup["dados"]
    assert fs.obter_filial_ativa()["id"] == "ad"
    fs.definir_filial_ativa("pn")
    restaurado = ss.obter_setor(setor["id"])
    assert restaurado["pdv_excluidos"] == [5]
    assert ss.obter_subgrupos_do_setor(setor["id"]) == {1: [10, 11]}


def test_importar_substitui_dados_existentes(temp_db):
    backup = bs.exportar()  # banco vazio
    _popular()
    bs.importar(backup)
    assert bs.exportar()["dados"]["setores"] == []


def test_arquivo_de_outro_formato_e_rejeitado(temp_db):
    with pytest.raises(ValidationError):
        bs.importar({"foo": "bar"})


def test_registro_inconsistente_nao_altera_nada(temp_db):
    _popular()
    antes = bs.exportar()
    ruim = bs.exportar()
    ruim["dados"]["metas"][0]["setor_id"] = 999  # setor inexistente
    with pytest.raises(ValidationError):
        bs.importar(ruim)
    assert bs.exportar()["dados"] == antes["dados"]
