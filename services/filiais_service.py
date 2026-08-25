"""Filial ativa (multi-servidor SQL Server) — estado global do app, persistido no
SQLite local. Não é por sessão/usuário: o app não tem login, roda numa máquina por vez,
então a última filial escolhida vale pra todo mundo até alguém trocar de novo."""

from config import Config
from database.sqlite import get_connection
from services.errors import ValidationError

_CHAVE_FILIAL_ATIVA = "filial_ativa"


def _buscar_filial(filial_id: str) -> dict | None:
    return next((f for f in Config.FILIAIS if f["id"] == filial_id), None)


def obter_filial_ativa() -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_FILIAL_ATIVA,)
        ).fetchone()
    filial = _buscar_filial(row["valor"]) if row else None
    return filial or Config.FILIAIS[0]


def listar_filiais() -> list[dict]:
    ativa_id = obter_filial_ativa()["id"]
    return [dict(f, ativa=(f["id"] == ativa_id)) for f in Config.FILIAIS]


def definir_filial_ativa(filial_id: str) -> dict:
    filial = _buscar_filial(filial_id)
    if filial is None:
        raise ValidationError("Filial inválida.")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO app_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (_CHAVE_FILIAL_ATIVA, filial_id),
        )
    return filial
