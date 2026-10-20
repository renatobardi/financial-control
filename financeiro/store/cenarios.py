import json
from typing import NamedTuple

import psycopg


class Cenario(NamedTuple):
    id: int
    nome: str
    fator_pessoas: int
    fator_compras: int
    trimestres: int
    escala_tipo: str
    escala_ref: int | None
    escala_valor_centavos: int | None
    elemento_tipo: str
    incluidos: list[str]


_COLUNAS = (
    "id, nome, fator_pessoas, fator_compras, trimestres, escala_tipo, escala_ref,"
    " escala_valor_centavos, elemento_tipo, incluidos"
)


def _ler(linha: tuple) -> Cenario:
    return Cenario(*linha[:-1], json.loads(linha[-1]))


def listar(conexao: psycopg.Connection, bd_id: int) -> list[Cenario]:
    linhas = conexao.execute(
        f"SELECT {_COLUNAS} FROM cenario WHERE bd_id = %s ORDER BY id", (bd_id,)
    ).fetchall()
    return [_ler(linha) for linha in linhas]


def achar(conexao: psycopg.Connection, bd_id: int, cenario_id: int) -> Cenario | None:
    linha = conexao.execute(
        f"SELECT {_COLUNAS} FROM cenario WHERE bd_id = %s AND id = %s", (bd_id, cenario_id)
    ).fetchone()
    return _ler(linha) if linha else None


def criar(
    conexao: psycopg.Connection,
    bd_id: int,
    nome: str,
    fator_pessoas: int,
    fator_compras: int,
    trimestres: int = 15,
    escala_tipo: str = "PDD",
    escala_ref: int | None = None,
    escala_valor: int | None = None,
    elemento_tipo: str = "Agrupamento",
    incluidos: list[str] | None = None,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO cenario (bd_id, nome, fator_pessoas, fator_compras, trimestres, escala_tipo,"
        " escala_ref, escala_valor_centavos, elemento_tipo, incluidos)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            bd_id,
            nome,
            fator_pessoas,
            fator_compras,
            trimestres,
            escala_tipo,
            escala_ref,
            escala_valor,
            elemento_tipo,
            json.dumps(incluidos or []),
        ),  # fmt: skip
    )
    conexao.commit()
    return cursor.fetchone()[0]


def atualizar(conexao: psycopg.Connection, bd_id: int, cenario_id: int, **campos: object) -> None:
    permitidos = {
        "nome", "fator_pessoas", "fator_compras", "trimestres", "escala_tipo", "escala_ref",
        "escala_valor_centavos", "elemento_tipo", "incluidos",
    }  # fmt: skip
    if not set(campos) <= permitidos:
        raise ValueError(f"campos desconhecidos: {sorted(set(campos) - permitidos)}")
    if "incluidos" in campos:
        campos["incluidos"] = json.dumps(campos["incluidos"])
    conexao.execute(
        f"UPDATE cenario SET {', '.join(f'{c} = %s' for c in campos)} WHERE bd_id = %s AND id = %s",
        (*campos.values(), bd_id, cenario_id),
    )
    conexao.commit()


def remover(conexao: psycopg.Connection, bd_id: int, cenario_id: int) -> None:
    conexao.execute(
        "DELETE FROM vaga_inicio WHERE bd_id = %s AND cenario_id = %s", (bd_id, cenario_id)
    )
    conexao.execute("DELETE FROM cenario WHERE bd_id = %s AND id = %s", (bd_id, cenario_id))
    conexao.commit()


def definir_inicio_vaga(
    conexao: psycopg.Connection, bd_id: int, cenario_id: int, vaga_id: int, mes: str
) -> None:
    conexao.execute(
        "INSERT INTO vaga_inicio (bd_id, cenario_id, vaga_id, mes) VALUES (%s, %s, %s, %s)"
        " ON CONFLICT (bd_id, cenario_id, vaga_id) DO UPDATE SET mes = excluded.mes",
        (bd_id, cenario_id, vaga_id, mes),
    )
    conexao.commit()


def inicios_de_vaga(conexao: psycopg.Connection, bd_id: int, cenario_id: int) -> dict[int, str]:
    linhas = conexao.execute(
        "SELECT vaga_id, mes FROM vaga_inicio WHERE bd_id = %s AND cenario_id = %s",
        (bd_id, cenario_id),
    ).fetchall()
    return dict(linhas)


def mapa_temas(conexao: psycopg.Connection, bd_id: int) -> dict[int, tuple]:
    """{tema_id: (demanda_id, iniciativa_id, tipo, agrupamento_id, squad_id)}."""
    linhas = conexao.execute(
        "SELECT t.id, d.id, d.iniciativa_id, d.tipo, t.agrupamento_id, d.squad_id FROM tema t"
        " JOIN demanda d ON d.bd_id = t.bd_id AND d.id = t.demanda_id WHERE t.bd_id = %s",
        (bd_id,),
    ).fetchall()
    return {t: (d, i, tipo, a, s) for t, d, i, tipo, a, s in linhas}
