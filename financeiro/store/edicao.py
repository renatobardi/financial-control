"""Edição simples de cadastros: renomear e trocar o nível do cargo."""

import sqlite3

# Cada tabela editável tem o seu SQL fixo: nome de tabela nunca vem de fora.
_RENOMEAR = {
    "empresa": "UPDATE empresa SET nome = ? WHERE bd_id = ? AND id = ?",
    "cargo": "UPDATE cargo SET nome = ? WHERE bd_id = ? AND id = ?",
    "iniciativa": "UPDATE iniciativa SET nome = ? WHERE bd_id = ? AND id = ?",
    "demanda": "UPDATE demanda SET nome = ? WHERE bd_id = ? AND id = ?",
    "tema": "UPDATE tema SET nome = ? WHERE bd_id = ? AND id = ?",
    "agrupamento": "UPDATE agrupamento SET nome = ? WHERE bd_id = ? AND id = ?",
    "fornecedor": "UPDATE fornecedor SET nome = ? WHERE bd_id = ? AND id = ?",
}
RENOMEAVEIS = frozenset(_RENOMEAR)


def renomear(
    conexao: sqlite3.Connection, tabela: str, bd_id: int, registro_id: int, nome: str
) -> None:
    if tabela not in _RENOMEAR:
        raise ValueError(f"tabela não editável: {tabela!r}")
    conexao.execute(_RENOMEAR[tabela], (nome, bd_id, registro_id))
    conexao.commit()


def alterar_nivel_cargo(conexao: sqlite3.Connection, bd_id: int, cargo_id: int, nivel: str) -> None:
    conexao.execute(
        "UPDATE cargo SET nivel = ? WHERE bd_id = ? AND id = ?", (nivel, bd_id, cargo_id)
    )
    conexao.commit()


# (tabela, coluna) que a tela pode trocar, cada um com o seu SQL fixo.
_DEFINIR = {
    ("empresa", "tipo"): "UPDATE empresa SET tipo = ? WHERE bd_id = ? AND id = ?",
    ("cargo", "nivel"): "UPDATE cargo SET nivel = ? WHERE bd_id = ? AND id = ?",
    ("demanda", "tipo"): "UPDATE demanda SET tipo = ? WHERE bd_id = ? AND id = ?",
    ("demanda", "iniciativa_id"): "UPDATE demanda SET iniciativa_id = ? WHERE bd_id = ? AND id = ?",
    ("tema", "agrupamento_id"): "UPDATE tema SET agrupamento_id = ? WHERE bd_id = ? AND id = ?",
    ("tema", "demanda_id"): "UPDATE tema SET demanda_id = ? WHERE bd_id = ? AND id = ?",
}


def definir(
    conexao: sqlite3.Connection,
    tabela: str,
    coluna: str,
    bd_id: int,
    registro_id: int,
    valor: object,
) -> None:
    sql = _DEFINIR.get((tabela, coluna))
    if sql is None:
        raise ValueError(f"campo não editável: {tabela}.{coluna}")
    conexao.execute(sql, (valor, bd_id, registro_id))
    conexao.commit()
