"""Testa a detecção/resolução de porta ocupada (seção: outro sistema Flask
já rodando na mesma máquina)."""

import socket

import pytest

from rede import porta_disponivel, resolver_porta


@pytest.fixture
def porta_ocupada():
    """Ocupa uma porta livre de verdade e devolve o número dela."""
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    porta = servidor.getsockname()[1]
    yield porta
    servidor.close()


def test_porta_disponivel_quando_livre():
    # porta alta improvável de estar em uso durante o teste
    assert porta_disponivel("127.0.0.1", 58123) is True


def test_porta_disponivel_falso_quando_ocupada(porta_ocupada):
    assert porta_disponivel("127.0.0.1", porta_ocupada) is False


def test_resolver_porta_pula_a_ocupada(porta_ocupada):
    resolvida = resolver_porta("127.0.0.1", porta_ocupada)
    assert resolvida != porta_ocupada
    assert resolvida > porta_ocupada


def test_resolver_porta_retorna_a_preferida_se_livre():
    assert resolver_porta("127.0.0.1", 58201) == 58201


def test_resolver_porta_esgota_tentativas_gera_erro(porta_ocupada, monkeypatch):
    # força todas as tentativas a "falharem" simulando que tudo está ocupado
    monkeypatch.setattr("rede.porta_disponivel", lambda host, porta: False)
    with pytest.raises(RuntimeError):
        resolver_porta("127.0.0.1", porta_ocupada, tentativas=3)
