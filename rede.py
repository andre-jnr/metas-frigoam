"""Utilitário de rede: detecta e resolve conflito de porta na inicialização.

Isolado do app.py (sem depender de Flask/config) para ser testável sem
inicializar a aplicação inteira.
"""

import socket


def porta_disponivel(host: str, porta: int) -> bool:
    endereco = "" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((endereco, porta))
            return True
        except OSError:
            return False


def resolver_porta(host: str, porta_preferida: int, tentativas: int = 20) -> int:
    """Se a porta preferida já estiver em uso (ex: outro sistema Flask rodando
    nesta máquina), procura a próxima porta livre em sequência."""
    for offset in range(tentativas):
        candidata = porta_preferida + offset
        if porta_disponivel(host, candidata):
            return candidata
    raise RuntimeError(
        f"Nenhuma porta livre encontrada entre {porta_preferida} e {porta_preferida + tentativas - 1}."
    )
