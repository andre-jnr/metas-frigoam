"""Login do sistema: usuários no SQLite (só o hash da senha) e o superusuário vindo do .env.

O superusuário é definido por ADMIN_USUARIO / ADMIN_SENHA no .env (a senha nunca fica no
código). A cada inicialização ele é criado ou tem a senha atualizada; trocar a senha no
.env encerra as sessões abertas, porque a sessão guarda um pedaço do hash vigente.

A sessão dura SESSAO_HORAS a partir do login, mesmo que a pessoa continue usando o
sistema: depois disso é preciso entrar de novo."""

import re
import secrets
import sqlite3
import threading
import time
from datetime import timedelta
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database.sqlite import get_connection
from services.errors import ValidationError

SESSAO_HORAS = 8
DURACAO_SESSAO = timedelta(hours=SESSAO_HORAS)

# Proteção contra tentativa e erro: depois de MAX_FALHAS senhas erradas seguidas, o
# endereço fica bloqueado por BLOQUEIO_SEGUNDOS.
MAX_FALHAS = 5
BLOQUEIO_SEGUNDOS = 5 * 60
_falhas: dict[str, dict] = {}
_lock_falhas = threading.Lock()


def chave_secreta() -> str:
    """SECRET_KEY do .env ou, se não houver, uma chave gerada uma vez e guardada em
    data/secret_key (fora do backup, para o arquivo exportado não carregar a chave)."""
    if Config.SECRET_KEY:
        return Config.SECRET_KEY
    arquivo = Path(Config.SQLITE_PATH).parent / "secret_key"
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8").strip()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    chave = secrets.token_hex(32)
    arquivo.write_text(chave, encoding="utf-8")
    return chave


def garantir_superusuario() -> bool:
    """Cria/atualiza o superusuário do .env. Retorna False se o .env não define um."""
    usuario = (Config.ADMIN_USUARIO or "").strip().lower()
    senha = Config.ADMIN_SENHA or ""
    if not usuario or not senha:
        return False
    with get_connection() as conn:
        row = conn.execute("SELECT senha_hash FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        if row and check_password_hash(row["senha_hash"], senha):
            conn.execute(
                "UPDATE usuarios SET superusuario = 1, ativo = 1, pode_ver_valores = 1 WHERE usuario = ?", (usuario,)
            )
            return True
        conn.execute(
            """INSERT INTO usuarios (usuario, senha_hash, superusuario, pode_ver_valores) VALUES (?, ?, 1, 1)
               ON CONFLICT(usuario) DO UPDATE SET senha_hash = excluded.senha_hash,
                   superusuario = 1, ativo = 1, pode_ver_valores = 1, updated_at = datetime('now')""",
            (usuario, generate_password_hash(senha)),
        )
    return True


def existe_usuario() -> bool:
    with get_connection() as conn:
        return conn.execute("SELECT 1 FROM usuarios WHERE ativo = 1 LIMIT 1").fetchone() is not None


def _usuario(usuario: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND ativo = 1", ((usuario or "").strip().lower(),)
        ).fetchone()


def versao_senha(senha_hash: str) -> str:
    return senha_hash[-16:]


def segundos_bloqueado(origem: str) -> int:
    with _lock_falhas:
        registro = _falhas.get(origem)
        if not registro:
            return 0
        restante = registro.get("bloqueado_ate", 0) - time.time()
        return max(0, int(restante + 0.999))


def autenticar(usuario: str, senha: str, origem: str) -> dict | None:
    """Confere usuário e senha. Retorna os dados da sessão ou None (senha errada).
    Quem está bloqueado deve ser barrado antes, com segundos_bloqueado()."""
    row = _usuario(usuario)
    # check_password_hash roda mesmo sem usuário, para não revelar pelo tempo de resposta
    # quais nomes existem
    hash_alvo = row["senha_hash"] if row else generate_password_hash("senha-inexistente")
    valido = check_password_hash(hash_alvo, senha or "") and row is not None
    with _lock_falhas:
        if valido:
            _falhas.pop(origem, None)
        else:
            registro = _falhas.setdefault(origem, {"falhas": 0})
            registro["falhas"] += 1
            if registro["falhas"] >= MAX_FALHAS:
                registro["falhas"] = 0
                registro["bloqueado_ate"] = time.time() + BLOQUEIO_SEGUNDOS
    if not valido:
        return None
    return {
        "usuario": row["usuario"],
        "superusuario": bool(row["superusuario"]),
        "versao": versao_senha(row["senha_hash"]),
        "expira_em": time.time() + DURACAO_SESSAO.total_seconds(),
    }


def usuario_da_sessao(dados: dict) -> dict | None:
    """Usuário da sessão com as permissões atuais do banco, ou None se a sessão não vale
    mais (passou das 8 horas, senha trocada ou usuário desativado/excluído). Ler do banco
    a cada requisição faz uma mudança de permissão valer na hora."""
    if not dados or not dados.get("usuario"):
        return None
    if time.time() >= dados.get("expira_em", 0):
        return None
    row = _usuario(dados["usuario"])
    if row is None or versao_senha(row["senha_hash"]) != dados.get("versao"):
        return None
    return {
        "usuario": row["usuario"],
        "superusuario": bool(row["superusuario"]),
        "pode_ver_valores": bool(row["superusuario"]) or bool(row["pode_ver_valores"]),
        "formato_valores": row["formato_valores"] if row["formato_valores"] in FORMATOS_VALORES else FORMATO_PADRAO,
        "expira_em": dados["expira_em"],
    }


FORMATOS_VALORES = ("1", "2", "3", "inteiro")
FORMATO_PADRAO = "2"


def definir_formato_valores(usuario: str, formato) -> str:
    formato = str(formato or "").strip().lower()
    if formato not in FORMATOS_VALORES:
        raise ValidationError("Escolha 1, 2 ou 3 casas decimais, ou número inteiro.")
    with get_connection() as conn:
        conn.execute(
            "UPDATE usuarios SET formato_valores = ?, updated_at = datetime('now') WHERE usuario = ?",
            (formato, usuario),
        )
    return formato


# ---------- cadastro de usuários (tela do superusuário) ----------
USUARIO_VALIDO = re.compile(r"^[a-z0-9._-]{3,30}$")
SENHA_MINIMA = 6


def _usuario_publico(row) -> dict:
    return {
        "id": row["id"],
        "usuario": row["usuario"],
        "superusuario": bool(row["superusuario"]),
        "pode_ver_valores": bool(row["superusuario"]) or bool(row["pode_ver_valores"]),
        "ativo": bool(row["ativo"]),
        "do_env": row["usuario"] == (Config.ADMIN_USUARIO or "").strip().lower(),
        "created_at": row["created_at"],
    }


def listar_usuarios() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM usuarios ORDER BY superusuario DESC, usuario").fetchall()
    return [_usuario_publico(r) for r in rows]


def _obter_por_id(usuario_id: int):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()


def _validar_senha(senha: str) -> None:
    if len(senha or "") < SENHA_MINIMA:
        raise ValidationError(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")


def criar_usuario(usuario: str, senha: str, pode_ver_valores: bool, superusuario: bool = False) -> dict:
    usuario = (usuario or "").strip().lower()
    if not USUARIO_VALIDO.match(usuario):
        raise ValidationError("Usuário deve ter de 3 a 30 caracteres: letras sem acento, números, ponto, hífen ou _.")
    _validar_senha(senha)
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO usuarios (usuario, senha_hash, superusuario, pode_ver_valores) VALUES (?, ?, ?, ?)",
                (usuario, generate_password_hash(senha), int(bool(superusuario)),
                 int(bool(pode_ver_valores) or bool(superusuario))),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Já existe um usuário com esse nome.") from exc
        novo_id = cursor.lastrowid
    return _usuario_publico(_obter_por_id(novo_id))


def atualizar_usuario(
    usuario_id: int, quem_altera: str, pode_ver_valores: bool, superusuario: bool, ativo: bool,
    nova_senha: str | None = None,
) -> dict:
    """Superusuário vê valores sempre. O superusuário do .env e o próprio usuário logado
    não podem perder o acesso de superusuário nem ser desativados (evita trancar todos
    para fora do cadastro)."""
    row = _obter_por_id(usuario_id)
    if row is None:
        raise ValidationError("Usuário não encontrado.", status_code=404)
    protegido = row["usuario"] == (Config.ADMIN_USUARIO or "").strip().lower() or row["usuario"] == quem_altera
    if protegido and (not superusuario or not ativo):
        raise ValidationError("Este usuário não pode deixar de ser superusuário nem ser desativado.")
    campos = {
        "superusuario": int(bool(superusuario)),
        "pode_ver_valores": int(bool(pode_ver_valores) or bool(superusuario)),
        "ativo": int(bool(ativo)),
    }
    if nova_senha:
        _validar_senha(nova_senha)
        if row["usuario"] == (Config.ADMIN_USUARIO or "").strip().lower():
            raise ValidationError("A senha deste usuário é definida no arquivo .env do servidor.")
        campos["senha_hash"] = generate_password_hash(nova_senha)
    atribuicoes = ", ".join(f"{c} = ?" for c in campos)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE usuarios SET {atribuicoes}, updated_at = datetime('now') WHERE id = ?",
            (*campos.values(), usuario_id),
        )
    return _usuario_publico(_obter_por_id(usuario_id))


def excluir_usuario(usuario_id: int, quem_exclui: str) -> None:
    row = _obter_por_id(usuario_id)
    if row is None:
        raise ValidationError("Usuário não encontrado.", status_code=404)
    if row["usuario"] in (quem_exclui, (Config.ADMIN_USUARIO or "").strip().lower()):
        raise ValidationError("Este usuário não pode ser excluído.")
    with get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
