"""Escrita das cargas: upsert com diário (para desfazer), sem commit.

Quem chama (o motor de cargas) fecha a transação. Nomes de tabela e de coluna vêm só do
código dos layouts e são conferidos contra a lista abaixo e contra o esquema do banco.
"""

import json
import sqlite3
from typing import NamedTuple

# Tabelas que uma carga pode gravar ou desfazer, com a coluna que as liga ao BD.
TABELAS = frozenset(
    {
        "alocacao",
        "compra_mes",
        "pdd_revisao",
        "pdd_linha",
        "pessoa",
        "tarifa",
        "iniciativa",
        "demanda",
        "tema",
        "agrupamento",
    }
)
# (tabela, coluna) que os layouts usam para achar um registro pelo código do arquivo.
BUSCAS = frozenset(
    {
        ("pessoa", "matricula"),
        ("tema", "codigo"),
        ("org", "codigo"),
        ("cargo", "codigo"),
        ("empresa", "codigo"),
        ("iniciativa", "codigo"),
        ("demanda", "codigo"),
        ("compra", "numero"),
        ("agrupamento", "nome"),
    }
)


class Diario:
    """Mudanças feitas por uma carga: `(tabela, registro_id, antes)`; antes None = inserido."""

    def __init__(self) -> None:
        self.mudancas: list[tuple[str, int, dict | None]] = []


class Mudanca(NamedTuple):
    tabela: str
    registro_id: int
    antes: dict | None


# Tabelas que a carga só consulta (para validar linhas).
SO_LEITURA = frozenset({"compra", "cargo", "empresa", "org"})


def _colunas(conexao: sqlite3.Connection, tabela: str, escrita: bool = True) -> list[str]:
    permitidas = TABELAS if escrita else TABELAS | SO_LEITURA
    if tabela not in permitidas:
        raise ValueError(f"tabela fora das cargas: {tabela!r}")
    return [c[1] for c in conexao.execute(f"PRAGMA table_info({tabela})")]


def id_por(
    conexao: sqlite3.Connection, tabela: str, coluna: str, bd_id: int, valor: str
) -> int | None:
    if (tabela, coluna) not in BUSCAS:
        raise ValueError(f"busca não permitida: {tabela}.{coluna}")
    linha = conexao.execute(
        f"SELECT id FROM {tabela} WHERE bd_id = ? AND {coluna} = ?", (bd_id, valor)
    ).fetchone()
    return linha[0] if linha else None


def achar(
    conexao: sqlite3.Connection, tabela: str, bd_id: int, chave: dict[str, object]
) -> dict | None:
    colunas = _colunas(conexao, tabela, escrita=False)
    if not set(chave) <= set(colunas):
        raise ValueError(f"coluna desconhecida em {tabela}: {sorted(set(chave) - set(colunas))}")
    onde = " AND ".join(f"{c} = ?" for c in chave)
    linha = conexao.execute(
        f"SELECT {', '.join(colunas)} FROM {tabela} WHERE bd_id = ? AND {onde}",
        (bd_id, *chave.values()),
    ).fetchone()
    return dict(zip(colunas, linha, strict=True)) if linha else None


def inserir(
    conexao: sqlite3.Connection,
    diario: Diario,
    tabela: str,
    bd_id: int,
    valores: dict[str, object],
) -> int:
    colunas = _colunas(conexao, tabela)
    if not set(valores) <= set(colunas):
        raise ValueError(f"coluna desconhecida em {tabela}: {sorted(set(valores) - set(colunas))}")
    nomes = ["bd_id", *valores]
    cursor = conexao.execute(
        f"INSERT INTO {tabela} ({', '.join(nomes)}) VALUES ({', '.join('?' for _ in nomes)})",
        (bd_id, *valores.values()),
    )
    diario.mudancas.append((tabela, cursor.lastrowid, None))
    return cursor.lastrowid


def alterar(
    conexao: sqlite3.Connection,
    diario: Diario,
    tabela: str,
    bd_id: int,
    atual: dict,
    valores: dict[str, object],
) -> None:
    colunas = _colunas(conexao, tabela)
    if not set(valores) <= set(colunas):
        raise ValueError(f"coluna desconhecida em {tabela}: {sorted(set(valores) - set(colunas))}")
    antes = {c: atual[c] for c in valores}
    conexao.execute(
        f"UPDATE {tabela} SET {', '.join(f'{c} = ?' for c in valores)} WHERE bd_id = ? AND id = ?",
        (*valores.values(), bd_id, atual["id"]),
    )
    diario.mudancas.append((tabela, atual["id"], antes))


def upsert(
    conexao: sqlite3.Connection,
    diario: Diario,
    tabela: str,
    bd_id: int,
    chave: dict[str, object],
    valores: dict[str, object],
) -> str:
    """Insere ou atualiza o registro de `chave`. Devolve inserida, atualizada ou igual."""
    atual = achar(conexao, tabela, bd_id, chave)
    if atual is None:
        inserir(conexao, diario, tabela, bd_id, {**chave, **valores})
        return "inserida"
    mudou = {c: v for c, v in valores.items() if atual[c] != v}
    if not mudou:
        return "igual"
    alterar(conexao, diario, tabela, bd_id, atual, mudou)
    return "atualizada"


# ---------- carga, rejeições e diário ----------


def criar_carga(
    conexao: sqlite3.Connection, bd_id: int, layout: str, arquivo: str, usuario_id: int, em: str
) -> int:
    cursor = conexao.execute(
        "INSERT INTO carga (bd_id, layout, arquivo, usuario_id, em) VALUES (?, ?, ?, ?, ?)",
        (bd_id, layout, arquivo, usuario_id, em),
    )
    return cursor.lastrowid


def fechar_relatorio(
    conexao: sqlite3.Connection, bd_id: int, carga_id: int, contagens: dict[str, int]
) -> None:
    conexao.execute(
        "UPDATE carga SET lidas = ?, inseridas = ?, atualizadas = ?, iguais = ?, rejeitadas = ?,"
        " horas = ?, valor_centavos = ? WHERE bd_id = ? AND id = ?",
        (
            contagens["lidas"],
            contagens["inseridas"],
            contagens["atualizadas"],
            contagens["iguais"],
            contagens["rejeitadas"],
            contagens["horas"],
            contagens["valor_centavos"],
            bd_id,
            carga_id,
        ),
    )


def gravar_rejeicao(
    conexao: sqlite3.Connection,
    bd_id: int,
    carga_id: int,
    linha: int,
    regra: str,
    mensagem: str,
    dados: dict,
    aprovavel: bool,
    grupo: str | None,
) -> None:
    conexao.execute(
        "INSERT INTO carga_rejeicao (bd_id, carga_id, linha, regra, mensagem, dados_json,"
        " aprovavel, grupo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            bd_id,
            carga_id,
            linha,
            regra,
            mensagem,
            json.dumps(dados, ensure_ascii=False),
            int(aprovavel),
            grupo,
        ),
    )


def gravar_diario(conexao: sqlite3.Connection, bd_id: int, carga_id: int, diario: Diario) -> None:
    for tabela, registro_id, antes in diario.mudancas:
        conexao.execute(
            "INSERT INTO carga_mudanca (bd_id, carga_id, tabela, registro_id, antes_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (bd_id, carga_id, tabela, registro_id, None if antes is None else json.dumps(antes)),
        )


class CargaLida(NamedTuple):
    id: int
    layout: str
    arquivo: str
    usuario: str
    em: str
    lidas: int
    inseridas: int
    atualizadas: int
    iguais: int
    rejeitadas: int
    horas: int
    valor_centavos: int
    estado: str


_SELECT_CARGA = (
    "SELECT c.id, c.layout, c.arquivo, u.nome, c.em, c.lidas, c.inseridas, c.atualizadas,"
    " c.iguais, c.rejeitadas, c.horas, c.valor_centavos, c.estado"
    " FROM carga c JOIN usuario u ON u.id = c.usuario_id"
)


def listar_cargas(conexao: sqlite3.Connection, bd_id: int) -> list[CargaLida]:
    linhas = conexao.execute(
        _SELECT_CARGA + " WHERE c.bd_id = ? ORDER BY c.id DESC", (bd_id,)
    ).fetchall()
    return [CargaLida(*linha) for linha in linhas]


def achar_carga(conexao: sqlite3.Connection, bd_id: int, carga_id: int) -> CargaLida | None:
    linha = conexao.execute(
        _SELECT_CARGA + " WHERE c.bd_id = ? AND c.id = ?", (bd_id, carga_id)
    ).fetchone()
    return CargaLida(*linha) if linha else None


class RejeicaoLida(NamedTuple):
    id: int
    linha: int
    regra: str
    mensagem: str
    dados: dict
    aprovavel: bool
    grupo: str | None
    aprovada: bool


def rejeicoes_da_carga(
    conexao: sqlite3.Connection, bd_id: int, carga_id: int
) -> list[RejeicaoLida]:
    linhas = conexao.execute(
        "SELECT id, linha, regra, mensagem, dados_json, aprovavel, grupo, aprovada"
        " FROM carga_rejeicao WHERE bd_id = ? AND carga_id = ? ORDER BY id",
        (bd_id, carga_id),
    ).fetchall()
    return [
        RejeicaoLida(i, ln, rg, ms, json.loads(dj), bool(ap), gr, bool(aa))
        for i, ln, rg, ms, dj, ap, gr, aa in linhas
    ]


def mudancas_da_carga(conexao: sqlite3.Connection, bd_id: int, carga_id: int) -> list[Mudanca]:
    linhas = conexao.execute(
        "SELECT tabela, registro_id, antes_json FROM carga_mudanca"
        " WHERE bd_id = ? AND carga_id = ? ORDER BY id",
        (bd_id, carga_id),
    ).fetchall()
    return [Mudanca(t, r, None if a is None else json.loads(a)) for t, r, a in linhas]


def cargas_posteriores_que_tocam(
    conexao: sqlite3.Connection, bd_id: int, carga_id: int
) -> list[int]:
    """Ids de cargas ativas e posteriores que mexeram nos mesmos registros desta carga."""
    linhas = conexao.execute(
        "SELECT DISTINCT p.carga_id FROM carga_mudanca p"
        " JOIN carga_mudanca m ON m.bd_id = p.bd_id AND m.tabela = p.tabela"
        "   AND m.registro_id = p.registro_id"
        " JOIN carga c ON c.bd_id = p.bd_id AND c.id = p.carga_id"
        " WHERE p.bd_id = ? AND m.carga_id = ? AND p.carga_id > ? AND c.estado = 'ativa'",
        (bd_id, carga_id, carga_id),
    ).fetchall()
    return [linha[0] for linha in linhas]


def restaurar(
    conexao: sqlite3.Connection, bd_id: int, tabela: str, registro_id: int, antes: dict | None
) -> None:
    """Desfaz uma mudança: apaga o inserido ou volta os valores de antes."""
    colunas = _colunas(conexao, tabela)
    if antes is None:
        conexao.execute(f"DELETE FROM {tabela} WHERE bd_id = ? AND id = ?", (bd_id, registro_id))
        return
    if not set(antes) <= set(colunas):
        raise ValueError(f"coluna desconhecida em {tabela}")
    conexao.execute(
        f"UPDATE {tabela} SET {', '.join(f'{c} = ?' for c in antes)} WHERE bd_id = ? AND id = ?",
        (*antes.values(), bd_id, registro_id),
    )


def marcar_desfeita(conexao: sqlite3.Connection, bd_id: int, carga_id: int, em: str) -> None:
    conexao.execute(
        "UPDATE carga SET estado = 'desfeita', desfeita_em = ? WHERE bd_id = ? AND id = ?",
        (em, bd_id, carga_id),
    )


def mes_fechado(conexao: sqlite3.Connection, bd_id: int, mes: str) -> bool:
    return (
        conexao.execute(
            "SELECT 1 FROM mes_fechado WHERE bd_id = ? AND mes = ?", (bd_id, mes)
        ).fetchone()
        is not None
    )


def horas_dos_outros_temas(
    conexao: sqlite3.Connection, bd_id: int, pessoa_id: int, mes: str, temas: list[int]
) -> int:
    marcas = ", ".join("?" for _ in temas) or "NULL"
    return conexao.execute(
        "SELECT COALESCE(SUM(horas), 0) FROM alocacao"
        f" WHERE bd_id = ? AND pessoa_id = ? AND mes = ? AND tema_id NOT IN ({marcas})",
        (bd_id, pessoa_id, mes, *temas),
    ).fetchone()[0]


def mes_do_registro(
    conexao: sqlite3.Connection, bd_id: int, tabela: str, registro_id: int
) -> str | None:
    """Mês a que um registro de alocação ou de compra pertence (None para as demais tabelas)."""
    if tabela not in ("alocacao", "compra_mes"):
        return None
    linha = conexao.execute(
        f"SELECT mes FROM {tabela} WHERE bd_id = ? AND id = ?", (bd_id, registro_id)
    ).fetchone()
    return linha[0] if linha else None


def aprovar_rejeicoes(
    conexao: sqlite3.Connection, bd_id: int, carga_id: int, grupo: str
) -> list[RejeicaoLida]:
    """Marca como aprovadas as rejeições aprováveis e ainda pendentes do grupo e as devolve."""
    pendentes = [
        r
        for r in rejeicoes_da_carga(conexao, bd_id, carga_id)
        if r.grupo == grupo and r.aprovavel and not r.aprovada
    ]
    for r in pendentes:
        conexao.execute(
            "UPDATE carga_rejeicao SET aprovada = 1 WHERE bd_id = ? AND id = ?", (bd_id, r.id)
        )
    return pendentes


def somar_na_carga(
    conexao: sqlite3.Connection, bd_id: int, carga_id: int, campo: str, quantidade: int
) -> None:
    if campo not in ("inseridas", "atualizadas", "iguais", "rejeitadas", "horas"):
        raise ValueError(campo)
    conexao.execute(
        f"UPDATE carga SET {campo} = {campo} + ? WHERE bd_id = ? AND id = ?",
        (quantidade, bd_id, carga_id),
    )
