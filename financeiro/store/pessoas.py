from typing import NamedTuple

import psycopg


class VagaNaoAberta(Exception):
    """A vaga não existe neste BD, não está aberta ou a pessoa é de outro BD."""


class Pessoa(NamedTuple):
    id: int
    matricula: str
    nome: str
    org: str
    cargo: str
    tema: str
    admissao: str
    desligamento: str | None


class Vaga(NamedTuple):
    id: int
    codigo: str
    org_id: int
    tema_id: int
    cargo_id: int
    aberta_em: str
    estado: str
    pessoa_id: int | None


def criar_pessoa(
    conexao: psycopg.Connection,
    bd_id: int,
    matricula: str,
    nome: str,
    org_id: int,
    cargo_id: int,
    tema_id: int,
    admissao: str,
    desligamento: str | None,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO pessoa (bd_id, matricula, nome, org_id, cargo_id, tema_id, admissao,"
        " desligamento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (bd_id, matricula, nome, org_id, cargo_id, tema_id, admissao, desligamento),
    )
    conexao.commit()
    return cursor.fetchone()[0]


_SELECT_PESSOA = (
    "SELECT p.id, p.matricula, p.nome, o.nome, c.nome, t.codigo, p.admissao, p.desligamento"
    " FROM pessoa p"
    " JOIN org o ON o.bd_id = p.bd_id AND o.id = p.org_id"
    " JOIN cargo c ON c.bd_id = p.bd_id AND c.id = p.cargo_id"
    " JOIN tema t ON t.bd_id = p.bd_id AND t.id = p.tema_id"
)


def achar_pessoa(conexao: psycopg.Connection, bd_id: int, pessoa_id: int) -> Pessoa | None:
    linha = conexao.execute(
        _SELECT_PESSOA + " WHERE p.bd_id = %s AND p.id = %s", (bd_id, pessoa_id)
    ).fetchone()
    return Pessoa(*linha) if linha else None


def listar_pessoas(conexao: psycopg.Connection, bd_id: int) -> list[Pessoa]:
    linhas = conexao.execute(
        _SELECT_PESSOA + " WHERE p.bd_id = %s ORDER BY p.id", (bd_id,)
    ).fetchall()
    return [Pessoa(*linha) for linha in linhas]


def abrir_vaga(
    conexao: psycopg.Connection,
    bd_id: int,
    codigo: str,
    org_id: int,
    tema_id: int,
    cargo_id: int,
    aberta_em: str,
) -> int:
    cursor = conexao.execute(
        "INSERT INTO vaga (bd_id, codigo, org_id, tema_id, cargo_id, aberta_em)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (bd_id, codigo, org_id, tema_id, cargo_id, aberta_em),
    )
    conexao.commit()
    return cursor.fetchone()[0]


def listar_vagas(conexao: psycopg.Connection, bd_id: int) -> list[Vaga]:
    linhas = conexao.execute(
        "SELECT id, codigo, org_id, tema_id, cargo_id, aberta_em, estado, pessoa_id"
        " FROM vaga WHERE bd_id = %s ORDER BY id",
        (bd_id,),
    ).fetchall()
    return [Vaga(*linha) for linha in linhas]


def preencher_vaga(conexao: psycopg.Connection, bd_id: int, vaga_id: int, pessoa_id: int) -> None:
    try:
        cursor = conexao.execute(
            "UPDATE vaga SET estado = 'preenchida', pessoa_id = %s"
            " WHERE bd_id = %s AND id = %s AND estado = 'aberta'",
            (pessoa_id, bd_id, vaga_id),
        )
    except psycopg.errors.IntegrityError as erro:
        conexao.rollback()
        raise VagaNaoAberta(vaga_id) from erro
    if cursor.rowcount == 0:
        raise VagaNaoAberta(vaga_id)
    conexao.commit()


def cancelar_vaga(conexao: psycopg.Connection, bd_id: int, vaga_id: int) -> None:
    cursor = conexao.execute(
        "UPDATE vaga SET estado = 'cancelada' WHERE bd_id = %s AND id = %s AND estado = 'aberta'",
        (bd_id, vaga_id),
    )
    if cursor.rowcount == 0:
        raise VagaNaoAberta(vaga_id)
    conexao.commit()


class PessoaDetalhe(NamedTuple):
    id: int
    matricula: str
    nome: str
    org_id: int
    unidade: str
    cargo_id: int
    cargo: str
    empresa: str
    vinculo: str  # propria | consultoria
    tema_id: int
    tema: str
    admissao: str
    desligamento: str | None


def listar_detalhe(conexao: psycopg.Connection, bd_id: int) -> list[PessoaDetalhe]:
    linhas = conexao.execute(
        "SELECT p.id, p.matricula, p.nome, p.org_id, o.nome, p.cargo_id, c.nome, e.nome, e.tipo,"
        " p.tema_id, t.codigo, p.admissao, p.desligamento FROM pessoa p"
        " JOIN org o ON o.bd_id = p.bd_id AND o.id = p.org_id"
        " JOIN cargo c ON c.bd_id = p.bd_id AND c.id = p.cargo_id"
        " JOIN empresa e ON e.bd_id = c.bd_id AND e.id = c.empresa_id"
        " JOIN tema t ON t.bd_id = p.bd_id AND t.id = p.tema_id"
        " WHERE p.bd_id = %s ORDER BY p.nome",
        (bd_id,),
    ).fetchall()
    return [PessoaDetalhe(*linha) for linha in linhas]


def atualizar_pessoa(
    conexao: psycopg.Connection,
    bd_id: int,
    pessoa_id: int,
    org_id: int,
    cargo_id: int,
    tema_id: int,
    desligamento: str | None,
    nome: str | None = None,
) -> None:
    conexao.execute(
        "UPDATE pessoa SET org_id = %s, cargo_id = %s, tema_id = %s, desligamento = %s,"
        " nome = COALESCE(%s, nome) WHERE bd_id = %s AND id = %s",
        (org_id, cargo_id, tema_id, desligamento, nome, bd_id, pessoa_id),
    )
    conexao.commit()
