import sqlite3
from typing import NamedTuple

from financeiro.store.escopo import entre_bds


class Usuario(NamedTuple):
    id: int
    email: str
    nome: str
    senha_hash: str | None
    tema: str
    formato_valor: str
    tela_inicial: str
    bd_padrao_id: int | None


class BdDoUsuario(NamedTuple):
    id: int
    nome: str
    sigla: str
    papel: str


class Membro(NamedTuple):
    usuario_id: int
    email: str
    nome: str
    papel: str
    pendente: bool


def criar_bd(conexao: sqlite3.Connection, nome: str, sigla: str) -> int:
    cursor = conexao.execute("INSERT INTO bd (nome, sigla) VALUES (?, ?)", (nome, sigla))
    conexao.commit()
    return cursor.lastrowid


def criar_usuario(
    conexao: sqlite3.Connection, email: str, nome: str, senha_hash: str | None
) -> int:
    cursor = conexao.execute(
        "INSERT INTO usuario (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, senha_hash)
    )
    conexao.commit()
    return cursor.lastrowid


def achar_usuario_por_email(conexao: sqlite3.Connection, email: str) -> Usuario | None:
    linha = conexao.execute(
        "SELECT id, email, nome, senha_hash, tema, formato_valor, tela_inicial, bd_padrao_id"
        " FROM usuario WHERE email = ?",
        (email,),
    ).fetchone()
    return Usuario(*linha) if linha else None


def achar_usuario(conexao: sqlite3.Connection, usuario_id: int) -> Usuario | None:
    linha = conexao.execute(
        "SELECT id, email, nome, senha_hash, tema, formato_valor, tela_inicial, bd_padrao_id"
        " FROM usuario WHERE id = ?",
        (usuario_id,),
    ).fetchone()
    return Usuario(*linha) if linha else None


def nome_do_bd(conexao: sqlite3.Connection, bd_id: int) -> str | None:
    linha = conexao.execute("SELECT nome FROM bd WHERE id = ?", (bd_id,)).fetchone()
    return linha[0] if linha else None


def adicionar_membro(conexao: sqlite3.Connection, bd_id: int, usuario_id: int, papel: str) -> None:
    conexao.execute(
        "INSERT INTO membro (bd_id, usuario_id, papel) VALUES (?, ?, ?)",
        (bd_id, usuario_id, papel),
    )
    conexao.commit()


def papel_do(conexao: sqlite3.Connection, bd_id: int, usuario_id: int) -> str | None:
    linha = conexao.execute(
        "SELECT papel FROM membro WHERE bd_id = ? AND usuario_id = ?", (bd_id, usuario_id)
    ).fetchone()
    return linha[0] if linha else None


def membros_do_bd(conexao: sqlite3.Connection, bd_id: int) -> list[Membro]:
    linhas = conexao.execute(
        "SELECT u.id, u.email, u.nome, m.papel, u.senha_hash IS NULL"
        " FROM membro m JOIN usuario u ON u.id = m.usuario_id"
        " WHERE m.bd_id = ? ORDER BY u.nome",
        (bd_id,),
    ).fetchall()
    return [Membro(i, e, n, p, bool(pend)) for i, e, n, p, pend in linhas]


def alterar_papel(conexao: sqlite3.Connection, bd_id: int, usuario_id: int, papel: str) -> None:
    conexao.execute(
        "UPDATE membro SET papel = ? WHERE bd_id = ? AND usuario_id = ?",
        (papel, bd_id, usuario_id),
    )
    conexao.commit()


def remover_membro(conexao: sqlite3.Connection, bd_id: int, usuario_id: int) -> None:
    conexao.execute("DELETE FROM membro WHERE bd_id = ? AND usuario_id = ?", (bd_id, usuario_id))
    conexao.commit()


@entre_bds
def bds_do_usuario(conexao: sqlite3.Connection, usuario_id: int) -> list[BdDoUsuario]:
    """Os BDs a que o usuário pertence, para escolher o BD ao entrar."""
    linhas = conexao.execute(
        "SELECT b.id, b.nome, b.sigla, m.papel"
        " FROM membro m JOIN bd b ON b.id = m.bd_id"
        " WHERE m.usuario_id = ? ORDER BY b.id",
        (usuario_id,),
    ).fetchall()
    return [BdDoUsuario(*linha) for linha in linhas]


class BdSimples(NamedTuple):
    id: int
    nome: str
    sigla: str


class Pedido(NamedTuple):
    id: int
    bd_id: int
    usuario_id: int
    email: str
    nome: str
    motivo: str
    estado: str


def atualizar_perfil(conexao: sqlite3.Connection, usuario_id: int, nome: str) -> None:
    conexao.execute("UPDATE usuario SET nome = ? WHERE id = ?", (nome, usuario_id))
    conexao.commit()


def definir_senha(conexao: sqlite3.Connection, usuario_id: int, senha_hash: str) -> None:
    conexao.execute("UPDATE usuario SET senha_hash = ? WHERE id = ?", (senha_hash, usuario_id))
    conexao.commit()


def atualizar_preferencias(
    conexao: sqlite3.Connection,
    usuario_id: int,
    tema: str,
    formato_valor: str,
    tela_inicial: str,
    bd_padrao_id: int | None,
) -> None:
    conexao.execute(
        "UPDATE usuario SET tema = ?, formato_valor = ?, tela_inicial = ?, bd_padrao_id = ?"
        " WHERE id = ?",
        (tema, formato_valor, tela_inicial, bd_padrao_id, usuario_id),
    )
    conexao.commit()


def convidar(conexao: sqlite3.Connection, bd_id: int, email: str, papel: str) -> tuple[int, bool]:
    """Dá acesso ao BD. E-mail sem conta ganha uma conta pendente (sem senha).

    Devolve (usuario_id, conta_nova).
    """
    usuario = achar_usuario_por_email(conexao, email)
    conta_nova = usuario is None
    usuario_id = (
        criar_usuario(conexao, email, email.split("@")[0], None) if usuario is None else usuario.id
    )
    conexao.execute(
        "INSERT INTO membro (bd_id, usuario_id, papel) VALUES (?, ?, ?)"
        " ON CONFLICT (bd_id, usuario_id) DO UPDATE SET papel = excluded.papel",
        (bd_id, usuario_id, papel),
    )
    conexao.commit()
    return usuario_id, conta_nova


def contar_admins(conexao: sqlite3.Connection, bd_id: int) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM membro WHERE bd_id = ? AND papel = 'Admin'", (bd_id,)
    ).fetchone()[0]


def criar_pedido(
    conexao: sqlite3.Connection, bd_id: int, usuario_id: int, motivo: str, criado_em: str
) -> int:
    cursor = conexao.execute(
        "INSERT INTO pedido_acesso (bd_id, usuario_id, motivo, criado_em) VALUES (?, ?, ?, ?)",
        (bd_id, usuario_id, motivo, criado_em),
    )
    conexao.commit()
    return cursor.lastrowid


def pedidos_abertos(conexao: sqlite3.Connection, bd_id: int) -> list[Pedido]:
    linhas = conexao.execute(
        "SELECT p.id, p.bd_id, p.usuario_id, u.email, u.nome, p.motivo, p.estado"
        " FROM pedido_acesso p JOIN usuario u ON u.id = p.usuario_id"
        " WHERE p.bd_id = ? AND p.estado = 'aberto' ORDER BY p.id",
        (bd_id,),
    ).fetchall()
    return [Pedido(*linha) for linha in linhas]


def decidir_pedido(conexao: sqlite3.Connection, bd_id: int, pedido_id: int, estado: str) -> None:
    conexao.execute(
        "UPDATE pedido_acesso SET estado = ? WHERE id = ? AND bd_id = ?",
        (estado, pedido_id, bd_id),
    )
    conexao.commit()


def achar_pedido(conexao: sqlite3.Connection, bd_id: int, pedido_id: int) -> Pedido | None:
    linha = conexao.execute(
        "SELECT p.id, p.bd_id, p.usuario_id, u.email, u.nome, p.motivo, p.estado"
        " FROM pedido_acesso p JOIN usuario u ON u.id = p.usuario_id"
        " WHERE p.id = ? AND p.bd_id = ?",
        (pedido_id, bd_id),
    ).fetchone()
    return Pedido(*linha) if linha else None


@entre_bds
def pedidos_do_usuario(conexao: sqlite3.Connection, usuario_id: int) -> list[Pedido]:
    """Os pedidos do próprio usuário, em qualquer BD, para ele acompanhar."""
    linhas = conexao.execute(
        "SELECT p.id, p.bd_id, p.usuario_id, u.email, u.nome, p.motivo, p.estado"
        " FROM pedido_acesso p JOIN usuario u ON u.id = p.usuario_id"
        " WHERE p.usuario_id = ? ORDER BY p.id",
        (usuario_id,),
    ).fetchall()
    return [Pedido(*linha) for linha in linhas]


@entre_bds
def bds_sem_vinculo(conexao: sqlite3.Connection, usuario_id: int) -> list[BdSimples]:
    """BDs de que o usuário ainda não faz parte, para ele pedir acesso."""
    linhas = conexao.execute(
        "SELECT b.id, b.nome, b.sigla FROM bd b"
        " WHERE b.id NOT IN (SELECT bd_id FROM membro WHERE usuario_id = ?) ORDER BY b.id",
        (usuario_id,),
    ).fetchall()
    return [BdSimples(*linha) for linha in linhas]


def achar_bd_por_nome(conexao: sqlite3.Connection, nome: str) -> int | None:
    linha = conexao.execute("SELECT id FROM bd WHERE nome = ?", (nome,)).fetchone()
    return linha[0] if linha else None


def contar_usuarios(conexao: sqlite3.Connection) -> int:
    return conexao.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]


@entre_bds
def excluir_conta(conexao: sqlite3.Connection, usuario_id: int) -> None:
    """Encerra a conta: tira vínculos, pedidos e sessões e anonimiza o usuário.

    O registro fica (o histórico de fechamento, carga e compras aponta para ele), mas sem
    e-mail, senha nem nome: ninguém consegue entrar de novo com ele.
    """
    conexao.execute("DELETE FROM membro WHERE usuario_id = ?", (usuario_id,))
    conexao.execute("DELETE FROM pedido_acesso WHERE usuario_id = ?", (usuario_id,))
    conexao.execute("DELETE FROM sessao WHERE usuario_id = ?", (usuario_id,))
    conexao.execute(
        "UPDATE usuario SET email = ?, nome = ?, senha_hash = NULL, bd_padrao_id = NULL"
        " WHERE id = ?",
        (f"excluida-{usuario_id}@invalido", "Conta excluída", usuario_id),
    )
    conexao.commit()


@entre_bds
def bds_em_que_e_ultimo_admin(conexao: sqlite3.Connection, usuario_id: int) -> list[int]:
    """BDs onde o usuário é o único Admin: ele não pode sair nem excluir a conta."""
    linhas = conexao.execute(
        "SELECT m.bd_id FROM membro m WHERE m.usuario_id = ? AND m.papel = 'Admin'"
        " AND (SELECT COUNT(*) FROM membro x WHERE x.bd_id = m.bd_id AND x.papel = 'Admin') = 1",
        (usuario_id,),
    ).fetchall()
    return [x[0] for x in linhas]
