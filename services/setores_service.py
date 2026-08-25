"""CRUD de setores e associação setor <-> grupo de produto (SQLite local)."""

import sqlite3

from database.sqlite import get_connection
from services import filiais_service
from services.errors import ValidationError

DIAS_SEMANA = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")


def _serializar_lista(valores: list[int] | None) -> str | None:
    if not valores:
        return None
    return ",".join(str(v) for v in sorted(set(int(v) for v in valores)))


def _desserializar_lista(texto: str | None) -> list[int]:
    if not texto:
        return []
    return [int(v) for v in texto.split(",") if v.strip() != ""]


def _setor_to_dict(row: sqlite3.Row, grupos_count: int = 0, tem_subgrupo: bool = False) -> dict:
    pdv_incluidos = _desserializar_lista(row["pdv_incluidos"])
    pdv_excluidos = _desserializar_lista(row["pdv_excluidos"])
    dias_semana_excluidos = _desserializar_lista(row["dias_semana_excluidos"])
    return {
        "id": row["id"],
        "nome": row["nome"],
        "descricao": row["descricao"],
        "ativo": bool(row["ativo"]),
        "ordem_exibicao": row["ordem_exibicao"],
        "grupos_count": grupos_count,
        "pdv_incluidos": pdv_incluidos,
        "pdv_excluidos": pdv_excluidos,
        "dias_semana_excluidos": dias_semana_excluidos,
        "tem_filtro_pdv": bool(pdv_incluidos or pdv_excluidos or dias_semana_excluidos),
        "tem_filtro_subgrupo": tem_subgrupo,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def listar_setores(apenas_ativos: bool = False) -> list[dict]:
    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        sql = "SELECT * FROM setores WHERE filial_id = ?"
        params: list = [filial_id]
        if apenas_ativos:
            sql += " AND ativo = 1"
        sql += " ORDER BY ordem_exibicao ASC, nome ASC"
        setores = conn.execute(sql, params).fetchall()

        contagens = dict(
            conn.execute("SELECT setor_id, COUNT(*) AS qtd FROM setor_grupo GROUP BY setor_id").fetchall()
        )
        setores_com_subgrupo = {
            r["setor_id"]
            for r in conn.execute("SELECT DISTINCT setor_id FROM setor_subgrupo").fetchall()
        }
        return [
            _setor_to_dict(s, contagens.get(s["id"], 0), s["id"] in setores_com_subgrupo) for s in setores
        ]


def obter_setor(setor_id: int) -> dict | None:
    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM setores WHERE id = ? AND filial_id = ?", (setor_id, filial_id)
        ).fetchone()
        if not row:
            return None
        qtd = conn.execute(
            "SELECT COUNT(*) FROM setor_grupo WHERE setor_id = ?", (setor_id,)
        ).fetchone()[0]
        tem_subgrupo = (
            conn.execute(
                "SELECT COUNT(*) FROM setor_subgrupo WHERE setor_id = ?", (setor_id,)
            ).fetchone()[0]
            > 0
        )
        return _setor_to_dict(row, qtd, tem_subgrupo)


def _validar_nome(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ValidationError("O nome do setor é obrigatório.")
    if len(nome) > 100:
        raise ValidationError("O nome do setor deve ter no máximo 100 caracteres.")
    return nome


def _validar_pdvs(valores: list[int] | None, campo: str) -> list[int] | None:
    if not valores:
        return None
    try:
        codigos = [int(v) for v in valores]
    except (TypeError, ValueError):
        raise ValidationError(f"{campo}: informe apenas códigos de PDV numéricos.")
    if any(c <= 0 for c in codigos):
        raise ValidationError(f"{campo}: códigos de PDV devem ser números positivos.")
    return codigos


def _validar_dias_semana(valores: list[int] | None) -> list[int] | None:
    if not valores:
        return None
    try:
        dias = [int(v) for v in valores]
    except (TypeError, ValueError):
        raise ValidationError("Dias da semana excluídos: valor inválido.")
    if any(d < 0 or d > 6 for d in dias):
        raise ValidationError("Dias da semana excluídos: use valores de 0 (Segunda) a 6 (Domingo).")
    return dias


def _validar_pdv_incluidos_excluidos(pdv_incluidos, pdv_excluidos) -> None:
    if pdv_incluidos and pdv_excluidos and set(pdv_incluidos) & set(pdv_excluidos):
        raise ValidationError("Um mesmo PDV não pode estar em 'incluídos' e 'excluídos' ao mesmo tempo.")


def criar_setor(
    nome: str,
    descricao: str = "",
    ordem_exibicao: int = 0,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
) -> dict:
    nome = _validar_nome(nome)
    pdv_incluidos = _validar_pdvs(pdv_incluidos, "PDVs incluídos")
    pdv_excluidos = _validar_pdvs(pdv_excluidos, "PDVs excluídos")
    dias_semana_excluidos = _validar_dias_semana(dias_semana_excluidos)
    _validar_pdv_incluidos_excluidos(pdv_incluidos, pdv_excluidos)
    filial_id = filiais_service.obter_filial_ativa()["id"]

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO setores (nome, descricao, ordem_exibicao, pdv_incluidos, pdv_excluidos, dias_semana_excluidos, filial_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    nome, (descricao or "").strip(), int(ordem_exibicao or 0),
                    _serializar_lista(pdv_incluidos), _serializar_lista(pdv_excluidos), _serializar_lista(dias_semana_excluidos),
                    filial_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f'Já existe um setor chamado "{nome}".') from exc
        setor_id = cursor.lastrowid
    return obter_setor(setor_id)


def atualizar_setor(
    setor_id: int,
    nome: str,
    descricao: str = "",
    ordem_exibicao: int = 0,
    pdv_incluidos: list[int] | None = None,
    pdv_excluidos: list[int] | None = None,
    dias_semana_excluidos: list[int] | None = None,
) -> dict:
    if obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    nome = _validar_nome(nome)
    pdv_incluidos = _validar_pdvs(pdv_incluidos, "PDVs incluídos")
    pdv_excluidos = _validar_pdvs(pdv_excluidos, "PDVs excluídos")
    dias_semana_excluidos = _validar_dias_semana(dias_semana_excluidos)
    _validar_pdv_incluidos_excluidos(pdv_incluidos, pdv_excluidos)

    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        try:
            conn.execute(
                """UPDATE setores SET nome = ?, descricao = ?, ordem_exibicao = ?,
                   pdv_incluidos = ?, pdv_excluidos = ?, dias_semana_excluidos = ?,
                   updated_at = datetime('now') WHERE id = ? AND filial_id = ?""",
                (
                    nome, (descricao or "").strip(), int(ordem_exibicao or 0),
                    _serializar_lista(pdv_incluidos), _serializar_lista(pdv_excluidos), _serializar_lista(dias_semana_excluidos),
                    setor_id, filial_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f'Já existe um setor chamado "{nome}".') from exc
    return obter_setor(setor_id)


def alternar_ativo(setor_id: int, ativo: bool) -> dict:
    if obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        conn.execute(
            "UPDATE setores SET ativo = ?, updated_at = datetime('now') WHERE id = ? AND filial_id = ?",
            (1 if ativo else 0, setor_id, filial_id),
        )
    return obter_setor(setor_id)


def excluir_setor(setor_id: int) -> None:
    if obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    filial_id = filiais_service.obter_filial_ativa()["id"]
    with get_connection() as conn:
        conn.execute("DELETE FROM setores WHERE id = ? AND filial_id = ?", (setor_id, filial_id))


def obter_grupos_do_setor(setor_id: int) -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT grupo_codigo FROM setor_grupo WHERE setor_id = ? ORDER BY grupo_codigo", (setor_id,)
        ).fetchall()
        return [r["grupo_codigo"] for r in rows]


def definir_grupos_do_setor(setor_id: int, grupo_codigos: list[int]) -> list[int]:
    """Substitui a associação completa do setor pelos códigos informados (deduplicados)."""
    if obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)
    codigos_unicos = sorted({int(c) for c in grupo_codigos})
    with get_connection() as conn:
        conn.execute("DELETE FROM setor_grupo WHERE setor_id = ?", (setor_id,))
        conn.executemany(
            "INSERT INTO setor_grupo (setor_id, grupo_codigo) VALUES (?, ?)",
            [(setor_id, codigo) for codigo in codigos_unicos],
        )
    return codigos_unicos


def obter_grupos_por_setores(setor_ids: list[int]) -> dict[int, list[int]]:
    """Mapa setor_id -> lista de grupo_codigo, para múltiplos setores de uma vez."""
    if not setor_ids:
        return {}
    with get_connection() as conn:
        placeholders = ",".join("?" * len(setor_ids))
        rows = conn.execute(
            f"SELECT setor_id, grupo_codigo FROM setor_grupo WHERE setor_id IN ({placeholders})",
            tuple(setor_ids),
        ).fetchall()
    mapa: dict[int, list[int]] = {sid: [] for sid in setor_ids}
    for r in rows:
        mapa.setdefault(r["setor_id"], []).append(r["grupo_codigo"])
    return mapa


def obter_subgrupos_do_setor(setor_id: int) -> dict[int, list[int]]:
    """Mapa grupo_codigo -> lista de subgrupo_codigo (narrowing) para um setor.
    Grupo ausente do mapa = incluído por inteiro (sem restrição de subgrupo)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT grupo_codigo, subgrupo_codigo FROM setor_subgrupo WHERE setor_id = ? "
            "ORDER BY grupo_codigo, subgrupo_codigo",
            (setor_id,),
        ).fetchall()
    mapa: dict[int, list[int]] = {}
    for r in rows:
        mapa.setdefault(r["grupo_codigo"], []).append(r["subgrupo_codigo"])
    return mapa


def definir_subgrupos_do_setor(
    setor_id: int, subgrupos_por_grupo: dict, grupo_codigos_validos: list[int] | None = None
) -> dict[int, list[int]]:
    """Substitui a associação completa de subgrupos do setor. Quando
    grupo_codigos_validos é informado, descarta entradas de grupos que não
    estejam nessa lista (evita narrowing órfão de um grupo desmarcado)."""
    if obter_setor(setor_id) is None:
        raise ValidationError("Setor não encontrado.", status_code=404)

    validos = set(grupo_codigos_validos) if grupo_codigos_validos is not None else None
    pares: list[tuple[int, int, int]] = []
    for grupo, subs in (subgrupos_por_grupo or {}).items():
        grupo_int = int(grupo)
        if validos is not None and grupo_int not in validos:
            continue
        for sub in {int(s) for s in subs}:
            pares.append((setor_id, grupo_int, sub))

    with get_connection() as conn:
        conn.execute("DELETE FROM setor_subgrupo WHERE setor_id = ?", (setor_id,))
        conn.executemany(
            "INSERT INTO setor_subgrupo (setor_id, grupo_codigo, subgrupo_codigo) VALUES (?, ?, ?)",
            pares,
        )
    return obter_subgrupos_do_setor(setor_id)


def obter_subgrupos_por_setores(setor_ids: list[int]) -> dict[int, dict[int, list[int]]]:
    """Mapa setor_id -> {grupo_codigo: [subgrupo_codigo,...]}, para múltiplos setores de uma vez."""
    if not setor_ids:
        return {}
    with get_connection() as conn:
        placeholders = ",".join("?" * len(setor_ids))
        rows = conn.execute(
            f"SELECT setor_id, grupo_codigo, subgrupo_codigo FROM setor_subgrupo WHERE setor_id IN ({placeholders})",
            tuple(setor_ids),
        ).fetchall()
    mapa: dict[int, dict[int, list[int]]] = {sid: {} for sid in setor_ids}
    for r in rows:
        mapa.setdefault(r["setor_id"], {}).setdefault(r["grupo_codigo"], []).append(r["subgrupo_codigo"])
    return mapa
