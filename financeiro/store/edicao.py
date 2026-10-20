"""Edição simples de cadastros: renomear e trocar o nível do cargo."""

import psycopg

# Cada tabela editável tem o seu SQL fixo: nome de tabela nunca vem de fora.
_RENOMEAR = {
    "empresa": "UPDATE empresa SET nome = %s WHERE bd_id = %s AND id = %s",
    "cargo": "UPDATE cargo SET nome = %s WHERE bd_id = %s AND id = %s",
    "iniciativa": "UPDATE iniciativa SET nome = %s WHERE bd_id = %s AND id = %s",
    "demanda": "UPDATE demanda SET nome = %s WHERE bd_id = %s AND id = %s",
    "tema": "UPDATE tema SET nome = %s WHERE bd_id = %s AND id = %s",
    "agrupamento": "UPDATE agrupamento SET nome = %s WHERE bd_id = %s AND id = %s",
    "fornecedor": "UPDATE fornecedor SET nome = %s WHERE bd_id = %s AND id = %s",
}
RENOMEAVEIS = frozenset(_RENOMEAR)


def renomear(
    conexao: psycopg.Connection, tabela: str, bd_id: int, registro_id: int, nome: str
) -> None:
    if tabela not in _RENOMEAR:
        raise ValueError(f"tabela não editável: {tabela!r}")
    conexao.execute(_RENOMEAR[tabela], (nome, bd_id, registro_id))
    conexao.commit()


def alterar_nivel_cargo(conexao: psycopg.Connection, bd_id: int, cargo_id: int, nivel: str) -> None:
    conexao.execute(
        "UPDATE cargo SET nivel = %s WHERE bd_id = %s AND id = %s", (nivel, bd_id, cargo_id)
    )
    conexao.commit()


# (tabela, coluna) que a tela pode trocar, cada um com o seu SQL fixo.
_DEFINIR = {
    ("empresa", "tipo"): "UPDATE empresa SET tipo = %s WHERE bd_id = %s AND id = %s",
    ("cargo", "nivel"): "UPDATE cargo SET nivel = %s WHERE bd_id = %s AND id = %s",
    ("demanda", "tipo"): "UPDATE demanda SET tipo = %s WHERE bd_id = %s AND id = %s",
    (
        "demanda",
        "iniciativa_id",
    ): "UPDATE demanda SET iniciativa_id = %s WHERE bd_id = %s AND id = %s",
    ("tema", "agrupamento_id"): "UPDATE tema SET agrupamento_id = %s WHERE bd_id = %s AND id = %s",
    ("tema", "demanda_id"): "UPDATE tema SET demanda_id = %s WHERE bd_id = %s AND id = %s",
}


def definir(
    conexao: psycopg.Connection,
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
