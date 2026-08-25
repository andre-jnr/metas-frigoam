import logging
from contextlib import contextmanager

import pyodbc

from config import Config

logger = logging.getLogger("dashboard_metas.sql_server")


class SqlServerError(Exception):
    """Erro amigável de conexão/consulta ao SQL Server (sem detalhes técnicos sensíveis)."""


@contextmanager
def get_connection(timeout: int = 10):
    # Import tardio: services.filiais_service depende de database.sqlite (SQLite
    # local), então importar no topo do módulo criaria um ciclo com este arquivo.
    from services import filiais_service

    filial = filiais_service.obter_filial_ativa()
    try:
        conn = pyodbc.connect(
            Config.sql_server_connection_string(filial["servidor"], filial["banco"]), timeout=timeout
        )
    except pyodbc.Error as exc:
        logger.error(
            "Falha ao conectar no SQL Server (%s/%s, filial=%s): %s",
            filial["servidor"], filial["banco"], filial["id"], exc,
        )
        raise SqlServerError(
            "Não foi possível conectar ao banco de dados. Verifique servidor, rede, credenciais e o serviço do SQL Server."
        ) from exc
    try:
        yield conn
    finally:
        conn.close()


def executar_query(sql: str, params: tuple = ()) -> list[dict]:
    """Executa um SELECT parametrizado e retorna uma lista de dicts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
        except pyodbc.Error as exc:
            logger.error("Erro ao executar consulta no SQL Server: %s", exc)
            raise SqlServerError("Erro ao consultar o banco de dados de vendas.") from exc
        colunas = [col[0] for col in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]


def testar_conexao() -> bool:
    try:
        with get_connection(timeout=5) as conn:
            conn.cursor().execute("SELECT 1")
        return True
    except SqlServerError:
        return False
