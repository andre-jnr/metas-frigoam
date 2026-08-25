import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SQL_SERVER = os.getenv("SQL_SERVER", "")
    SQL_DATABASE = os.getenv("SQL_DATABASE", "")
    SQL_USERNAME = os.getenv("SQL_USERNAME", "")
    SQL_PASSWORD = os.getenv("SQL_PASSWORD", "")
    SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")

    # Cada filial usa as mesmas credenciais (USERNAME/PASSWORD/DRIVER acima) e o mesmo
    # schema, mas servidor e banco podem variar por filial. "banco" cai de volta em
    # SQL_DATABASE quando a filial não define um banco próprio (Ponta Negra e Parque 10
    # usam o mesmo "sismoura"; Morada do Sol tem seu próprio "sismoura_srv").
    # SQL_SERVER_PN cai de volta em SQL_SERVER pra não quebrar quem já tinha só essa
    # variável configurada.
    FILIAIS = [
        {
            "id": "pn", "nome": "Ponta Negra",
            "servidor": os.getenv("SQL_SERVER_PN", os.getenv("SQL_SERVER", "server_pn")),
            "banco": os.getenv("SQL_DATABASE_PN", os.getenv("SQL_DATABASE", "sismoura")),
        },
        {
            "id": "prq10", "nome": "Parque 10",
            "servidor": os.getenv("SQL_SERVER_PRQ10", "serverprq10"),
            "banco": os.getenv("SQL_DATABASE_PRQ10", os.getenv("SQL_DATABASE", "sismoura")),
        },
        {
            "id": "ad", "nome": "Morada do Sol",
            "servidor": os.getenv("SQL_SERVER_AD", "serverad"),
            "banco": os.getenv("SQL_DATABASE_AD", "sismoura_srv"),
        },
    ]

    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "120"))

    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"

    SQLITE_PATH = BASE_DIR / os.getenv("SQLITE_PATH", "data/sistema.db")
    LOG_PATH = BASE_DIR / os.getenv("LOG_PATH", "logs/app.log")

    @classmethod
    def sql_server_connection_string(cls, servidor: str | None = None, banco: str | None = None) -> str:
        return (
            f"DRIVER={{{cls.SQL_DRIVER}}};"
            f"SERVER={servidor or cls.SQL_SERVER};"
            f"DATABASE={banco or cls.SQL_DATABASE};"
            f"UID={cls.SQL_USERNAME};"
            f"PWD={cls.SQL_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
