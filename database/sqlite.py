import logging
import sqlite3
from contextlib import contextmanager

from config import Config
from database.models import ALL_DDL, DDL_SETORES, MIGRACOES_SETORES

logger = logging.getLogger("dashboard_metas.sqlite")


def _aplicar_migracoes(conn: sqlite3.Connection) -> None:
    """Adiciona colunas novas em bancos criados por versões anteriores. Idempotente:
    ignora silenciosamente quando a coluna já existe."""
    for statement in MIGRACOES_SETORES:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def _migrar_setores_para_multi_filial(conn: sqlite3.Connection) -> None:
    """Bancos criados antes do suporte a multi-filial têm `setores.nome` único
    globalmente; a versão atual precisa de `filial_id` + `UNIQUE(filial_id, nome)`.
    SQLite não permite alterar essa constraint via ALTER TABLE, então recriamos a
    tabela. Idempotente: só roda se `filial_id` ainda não existir. Todo setor que já
    existia vira da filial 'pn' (Ponta Negra, única filial até aqui).

    IMPORTANTE sobre a ordem das operações: `ALTER TABLE setores RENAME TO X`
    reescreve automaticamente as cláusulas REFERENCES de `metas`/`setor_grupo`/
    `setor_subgrupo` pra apontar pro nome novo (X) — então criamos a tabela nova sob
    um nome temporário, copiamos os dados, DROPamos a `setores` antiga (que os filhos
    ainda referenciam pelo nome original, intocado) e só então renomeamos a tabela
    nova para `setores`, sem nunca renomear a tabela antiga. Mesmo assim mantemos
    foreign_keys=OFF durante toda a operação: com FK ligada, o DROP TABLE de uma
    tabela ainda referenciada por ON DELETE CASCADE apaga as linhas filhas de
    verdade (já vimos isso apagar todas as metas ao testar)."""
    colunas = [row[1] for row in conn.execute("PRAGMA table_info(setores)").fetchall()]
    if not colunas or "filial_id" in colunas:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    ddl_temp = DDL_SETORES.replace(
        "CREATE TABLE IF NOT EXISTS setores (", "CREATE TABLE setores_novo_migracao_filial (", 1
    )
    conn.executescript(ddl_temp)
    conn.execute(
        """INSERT INTO setores_novo_migracao_filial (id, nome, descricao, ativo, ordem_exibicao,
                                                       pdv_incluidos, pdv_excluidos, dias_semana_excluidos,
                                                       filial_id, created_at, updated_at)
           SELECT id, nome, descricao, ativo, ordem_exibicao,
                  pdv_incluidos, pdv_excluidos, dias_semana_excluidos, 'pn', created_at, updated_at
           FROM setores"""
    )
    conn.execute("DROP TABLE setores")
    conn.execute("ALTER TABLE setores_novo_migracao_filial RENAME TO setores")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def init_db(db_path=None) -> None:
    path = db_path or Config.SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in ALL_DDL:
            conn.executescript(statement)
        _aplicar_migracoes(conn)
        _migrar_setores_para_multi_filial(conn)
        conn.commit()
        logger.info("SQLite inicializado em %s", path)
    finally:
        conn.close()


@contextmanager
def get_connection(db_path=None):
    path = db_path or Config.SQLITE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
