import logging
import webbrowser
from logging.handlers import RotatingFileHandler
from threading import Timer

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from config import Config
from database.sql_server import SqlServerError
from database.sqlite import init_db
from rede import porta_disponivel, resolver_porta
from services.errors import ValidationError


def configurar_logging() -> None:
    Config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(Config.LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    logger = logging.getLogger("dashboard_metas")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console)


def create_app() -> Flask:
    configurar_logging()
    logger = logging.getLogger("dashboard_metas")

    app = Flask(__name__)
    app.json.sort_keys = False

    init_db()
    logger.info("Aplicação inicializada.")

    from routes.api import api_bp
    from routes.dashboard import dashboard_bp
    from routes.metas import metas_bp
    from routes.setores import setores_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(setores_bp)
    app.register_blueprint(metas_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return jsonify({"erro": err.mensagem}), err.status_code

    @app.errorhandler(SqlServerError)
    def handle_sql_server_error(err: SqlServerError):
        return jsonify({"erro": str(err)}), 503

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return err

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        logger.exception("Erro inesperado")
        return jsonify({"erro": "Ocorreu um erro inesperado. Consulte os logs para mais detalhes."}), 500

    return app


app = create_app()


def _abrir_navegador(porta: int) -> None:
    webbrowser.open(f"http://localhost:{porta}")


if __name__ == "__main__":
    logger = logging.getLogger("dashboard_metas")
    porta = Config.FLASK_PORT
    if not porta_disponivel(Config.FLASK_HOST, porta):
        nova_porta = resolver_porta(Config.FLASK_HOST, porta + 1)
        logger.warning(
            "Porta %s já está em uso (outro sistema pode estar rodando nesta máquina). Usando a porta %s.",
            porta, nova_porta,
        )
        porta = nova_porta

    if not Config.FLASK_DEBUG:
        Timer(1.2, _abrir_navegador, args=(porta,)).start()
    app.run(host=Config.FLASK_HOST, port=porta, debug=Config.FLASK_DEBUG)
